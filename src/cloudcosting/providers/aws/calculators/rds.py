"""RDS cost calculator."""

from cloudcosting.domain import CostLineItem, ResourceCost

HOURS_PER_MONTH = 730
REQUIRED_PARAMS = ("engine", "instance_class", "storage_gb")


def validate(params: dict) -> list[str]:
    """Validate RDS parameters. Returns list of error messages."""
    errors = []
    for field in REQUIRED_PARAMS:
        if field not in params:
            errors.append(f"RDS: missing required parameter '{field}'")
    if "storage_gb" in params:
        try:
            int(params["storage_gb"])
        except (ValueError, TypeError):
            errors.append(
                f"RDS: 'storage_gb' must be an integer, got '{params['storage_gb']}'"
            )
    return errors


# Fallback hourly prices when API is unavailable (us-east-1, Single-AZ)
# PostgreSQL / MySQL / MariaDB (open-source engines)
RDS_FALLBACK_POSTGRES = {
    "db.t3.micro": 0.018,
    "db.t3.small": 0.036,
    "db.t3.medium": 0.072,
    "db.t3.large": 0.145,
    "db.t3.xlarge": 0.29,
    "db.t3.2xlarge": 0.58,
    "db.r6g.large": 0.26,
    "db.r6g.xlarge": 0.52,
    "db.r6g.2xlarge": 1.04,
    "db.r6g.4xlarge": 2.08,
    "db.r6g.8xlarge": 4.16,
    "db.m6g.large": 0.178,
    "db.m6g.xlarge": 0.356,
    "db.m6g.2xlarge": 0.712,
    "db.r6i.large": 0.26,
    "db.r6i.xlarge": 0.52,
    "db.r6i.2xlarge": 1.04,
    "db.m6i.large": 0.178,
    "db.m6i.xlarge": 0.356,
    "db.m6i.2xlarge": 0.712,
}

# SQL Server SE license-included (significantly higher due to SQL Server license)
# SQL Server on RDS requires Intel-based instances (r6i, m6i, not Graviton r6g/m6g)
RDS_FALLBACK_SQLSERVER_SE = {
    "db.t3.micro": 0.047,
    "db.t3.small": 0.094,
    "db.t3.medium": 0.188,
    "db.t3.large": 0.376,
    "db.t3.xlarge": 0.752,
    "db.t3.2xlarge": 1.504,
    "db.r6i.large": 0.84,
    "db.r6i.xlarge": 1.38,
    "db.r6i.2xlarge": 2.46,
    "db.r6i.4xlarge": 4.62,
    "db.r6i.8xlarge": 8.94,
    "db.m6i.large": 0.634,
    "db.m6i.xlarge": 0.968,
    "db.m6i.2xlarge": 1.636,
    "db.m6i.4xlarge": 2.972,
    "db.m6i.8xlarge": 5.644,
}

# SQL Server BYOL (Bring Your Own License) -- base compute only, no license
# Prices are similar to open-source engines since no license is embedded
RDS_FALLBACK_SQLSERVER_BYOL = {
    "db.t3.micro": 0.018,
    "db.t3.small": 0.036,
    "db.t3.medium": 0.072,
    "db.t3.large": 0.145,
    "db.t3.xlarge": 0.29,
    "db.t3.2xlarge": 0.58,
    "db.r6i.large": 0.252,
    "db.r6i.xlarge": 0.504,
    "db.r6i.2xlarge": 1.008,
    "db.r6i.4xlarge": 2.016,
    "db.r6i.8xlarge": 4.032,
    "db.m6i.large": 0.178,
    "db.m6i.xlarge": 0.356,
    "db.m6i.2xlarge": 0.712,
    "db.m6i.4xlarge": 1.424,
    "db.m6i.8xlarge": 2.848,
}

# Engine-to-fallback-table mapping
# BYOL is indicated by engine + license_model param, handled in estimate()
RDS_FALLBACK_BY_ENGINE = {
    "postgres": RDS_FALLBACK_POSTGRES,
    "mysql": RDS_FALLBACK_POSTGRES,
    "mariadb": RDS_FALLBACK_POSTGRES,
    "sqlserver-se": RDS_FALLBACK_SQLSERVER_SE,
    "sqlserver-ee": RDS_FALLBACK_SQLSERVER_SE,
    "sqlserver-se-byol": RDS_FALLBACK_SQLSERVER_BYOL,
    "sqlserver-ee-byol": RDS_FALLBACK_SQLSERVER_BYOL,
}

STORAGE_FALLBACK_PRICES = {"gp3": 0.115, "gp2": 0.115, "io1": 0.125}


def estimate(params: dict, pricing_adapter, region: str, label: str) -> ResourceCost:
    """Calculate RDS costs given params and a pricing adapter."""
    engine = params["engine"]
    instance_class = params["instance_class"]
    storage_gb = int(params["storage_gb"])
    multi_az = bool(params.get("multi_az", False))
    storage_type = params.get("storage_type", "gp3")
    backup_retention_days = int(params.get("backup_retention_days", 7))

    license_model = params.get("license_model", "license-included")

    # Determine fallback table key based on engine + license model
    if license_model == "bring-your-own-license" and engine.startswith("sqlserver"):
        fallback_key = f"{engine}-byol"
    else:
        fallback_key = engine

    # Fetch instance pricing
    try:
        instance_data = pricing_adapter.get_price(
            service_code="AmazonRDS",
            filters={
                "instanceType": instance_class,
                "databaseEngine": _engine_name(engine),
                "deploymentOption": "Multi-AZ" if multi_az else "Single-AZ",
                "licenseModel": "Bring your own license"
                if license_model == "bring-your-own-license"
                else "No license required"
                if engine in ("postgres", "mysql", "mariadb")
                else "License included",
            },
            region=region,
        )
        fallback_table = RDS_FALLBACK_BY_ENGINE.get(fallback_key, RDS_FALLBACK_POSTGRES)
        hourly = _extract_hourly(instance_data) or fallback_table.get(
            instance_class, 0.50
        )
    except Exception:
        fallback_table = RDS_FALLBACK_BY_ENGINE.get(fallback_key, RDS_FALLBACK_POSTGRES)
        hourly = fallback_table.get(instance_class, 0.50)

    if multi_az:
        hourly *= 2  # Multi-AZ doubles instance cost

    instance_monthly = hourly * HOURS_PER_MONTH

    # Storage cost
    try:
        storage_data = pricing_adapter.get_price(
            service_code="AmazonRDS",
            filters={
                "volumeType": _storage_type_name(storage_type),
                "deploymentOption": "Multi-AZ" if multi_az else "Single-AZ",
            },
            region=region,
        )
        storage_per_gb = _extract_gb_month(storage_data) or STORAGE_FALLBACK_PRICES.get(
            storage_type, 0.115
        )
    except Exception:
        storage_per_gb = STORAGE_FALLBACK_PRICES.get(storage_type, 0.115)

    storage_monthly = storage_per_gb * storage_gb

    # Backup cost (simplified: beyond free tier of 100% of DB size)
    backup_monthly = 0.0
    if backup_retention_days > 0:
        backup_per_gb = 0.095
        extra_backup_gb = max(0, storage_gb * (backup_retention_days / 30) - storage_gb)
        backup_monthly = backup_per_gb * extra_backup_gb

    line_items = [
        CostLineItem(name="instance", monthly=instance_monthly),
        CostLineItem(name="storage", monthly=storage_monthly),
    ]
    notes = [f"Storage type: {storage_type}"]

    if license_model == "bring-your-own-license":
        notes.append("License: BYOL (existing SQL Server license required)")
    elif engine.startswith("sqlserver"):
        notes.append("License: Included in RDS pricing")

    if multi_az:
        notes.append("Multi-AZ: pricing reflects Multi-AZ deployment")

    if backup_monthly > 0:
        line_items.append(CostLineItem(name="backup", monthly=backup_monthly))
        notes.append(f"Backup retention: {backup_retention_days} days")

    monthly = sum(item.monthly for item in line_items)
    annual = monthly * 12

    return ResourceCost(
        label=label or f"RDS {engine} {instance_class}",
        type="rds",
        monthly=monthly,
        annual=annual,
        line_items=tuple(line_items),
        notes=tuple(notes),
    )


def _engine_name(engine: str) -> str:
    mapping = {
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
        "mariadb": "MariaDB",
        "sqlserver-se": "SQL Server",
        "sqlserver-ee": "SQL Server",
        "oracle-se2": "Oracle",
    }
    return mapping.get(engine, engine)


def _storage_type_name(storage_type: str) -> str:
    mapping = {
        "gp3": "General Purpose (SSD)",
        "gp2": "General Purpose",
        "io1": "Provisioned IOPS",
    }
    return mapping.get(storage_type, storage_type)


def _extract_hourly(data: dict) -> float:
    prices = data.get("prices", {})
    for unit_key in ("hrs", "hr", "hour", "hours"):
        if unit_key in prices:
            return prices[unit_key]["price"]
    # Fallback: take first price
    for entry in prices.values():
        return entry["price"]
    return 0.0


def _extract_gb_month(data: dict) -> float:
    prices = data.get("prices", {})
    for unit_key in ("gb-mo", "gb-month", "gb"):
        if unit_key in prices:
            return prices[unit_key]["price"]
    for entry in prices.values():
        return entry["price"]
    return 0.0


def _extract_backup_price(data: dict) -> float:
    # Simplified backup pricing estimate
    return 0.095
