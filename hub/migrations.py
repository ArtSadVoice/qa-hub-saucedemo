"""Schema migrations for Hub state files.

Three state files carry versioned shapes:
- config.json       (dict with top-level _schema_version)
- run_history.json  (list — implicit v1; wrap in {_schema_version, data} if we ever break shape)
- schedules.json    (list — implicit v1; same)

Each migrate_* function:
- accepts data loaded from the file
- applies sequential migrations to bring it to CURRENT_*_VERSION
- returns the migrated data (caller saves it back if it changed)

When introducing a breaking schema change:
1. Bump CURRENT_*_VERSION
2. Add an `if version < N:` branch that transforms the data
3. Update the save-side to stamp the new version
"""

CURRENT_CONFIG_VERSION = 1
CURRENT_HISTORY_VERSION = 1
CURRENT_SCHEDULES_VERSION = 1


def migrate_config(cfg: dict) -> dict:
    """Bring a config.json payload up to CURRENT_CONFIG_VERSION.
    Today the only migration is stamping the version on legacy files."""
    if not isinstance(cfg, dict):
        return {"_schema_version": CURRENT_CONFIG_VERSION, "projects": []}

    version = int(cfg.get("_schema_version", 0))
    # Future migrations go here — e.g.:
    # if version < 2:
    #     for p in cfg.get("projects", []):
    #         p.setdefault("new_required_field", default)
    #     version = 2
    cfg["_schema_version"] = CURRENT_CONFIG_VERSION
    return cfg


def migrate_history(entries: list) -> list:
    """Bring run_history.json entries up to CURRENT_HISTORY_VERSION.
    Shape today: flat list of dicts. Reserved for future shape change."""
    if not isinstance(entries, list):
        return []
    # Future migrations operate on each entry, e.g.:
    # for e in entries: e.setdefault("env", "uat")
    return entries


def migrate_schedules(entries: list) -> list:
    """Bring schedules.json entries up to CURRENT_SCHEDULES_VERSION.
    Shape today: flat list of dicts."""
    if not isinstance(entries, list):
        return []
    return entries
