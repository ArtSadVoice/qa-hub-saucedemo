"""Unit tests for config validation — runs at startup, must stay fast and reliable."""
from validators import validate_config


def test_clean_config_has_no_errors():
    cfg = {
        "_schema_version": 1,
        "projects": [
            {"id": "p1", "name": "P1", "path": "x/p1", "type": "full-pipeline", "phase": "active"},
        ],
    }
    assert validate_config(cfg) == []


def test_missing_required_field_is_reported():
    cfg = {"projects": [{"id": "p1", "name": "P1", "path": "x", "type": "full-pipeline"}]}
    assert validate_config(cfg) == []  # phase is optional
    cfg2 = {"projects": [{"id": "p1", "name": "P1", "type": "full-pipeline"}]}  # missing path
    errs = validate_config(cfg2)
    assert any("path" in e for e in errs)


def test_invalid_type_is_reported():
    cfg = {"projects": [{"id": "p1", "name": "P1", "path": "x", "type": "not-a-type"}]}
    errs = validate_config(cfg)
    assert any("type='not-a-type'" in e for e in errs)


def test_invalid_phase_is_reported():
    cfg = {"projects": [{"id": "p1", "name": "P1", "path": "x", "type": "full-pipeline", "phase": "paused-ish"}]}
    errs = validate_config(cfg)
    assert any("phase='paused-ish'" in e for e in errs)


def test_duplicate_id_is_reported():
    cfg = {"projects": [
        {"id": "same", "name": "A", "path": "a", "type": "full-pipeline"},
        {"id": "same", "name": "B", "path": "b", "type": "full-pipeline"},
    ]}
    errs = validate_config(cfg)
    assert any("duplicate id" in e for e in errs)


def test_duplicate_path_is_reported():
    cfg = {"projects": [
        {"id": "a", "name": "A", "path": "shared", "type": "full-pipeline"},
        {"id": "b", "name": "B", "path": "shared", "type": "full-pipeline"},
    ]}
    errs = validate_config(cfg)
    assert any("duplicate path" in e for e in errs)


def test_partial_smtp_config_is_reported():
    cfg = {"projects": [], "email": {"smtp_host": "smtp.example.com"}}  # missing user and port
    errs = validate_config(cfg)
    assert any("smtp_user" in e for e in errs)
    assert any("smtp_port" in e for e in errs)


def test_empty_email_section_is_ok():
    cfg = {"projects": [], "email": {}}
    assert validate_config(cfg) == []


def test_non_dict_root_fails_loud():
    assert validate_config([]) == ["config.json root is not an object"]
    assert validate_config("not a dict") == ["config.json root is not an object"]


def test_current_hub_config_is_valid(hub):
    """Smoke test: the live config.json must pass validation."""
    assert validate_config(hub.load_config()) == []
