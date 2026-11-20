"""Validation tests for manifest.json, hacs.json, translations, and brand assets."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import tomllib

from custom_components.calidad_aire_canarias.const import DOMAIN, USER_AGENT, VERSION

REPO_ROOT = Path(__file__).parent.parent
INTEGRATION_ROOT = REPO_ROOT / "custom_components" / DOMAIN
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _flatten_keys(data: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _flatten_keys(value, path)
        else:
            keys.add(path)
    return keys


def _png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == PNG_SIGNATURE
    assert header[12:16] == b"IHDR"
    width, height = struct.unpack(">II", header[16:24])
    return (width, height)


def test_manifest_keys_order_categories_and_version_parity() -> None:
    """Ensure manifest.json follows hassfest ordering, Marketplace categories, and version parity."""
    manifest = json.loads((INTEGRATION_ROOT / "manifest.json").read_text(encoding="utf-8"))
    keys = list(manifest.keys())

    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])
    assert manifest["domain"] == DOMAIN
    assert manifest["integration_type"] == "service"
    assert manifest["categories"] == ["weather_alerts.air_quality_pollen"]
    assert manifest["version"] == VERSION
    assert VERSION in USER_AGENT

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == VERSION


def test_translations_parity_and_no_strings_json() -> None:
    """Ensure en.json and es.json match 1:1, contain zero core refs, and no stale strings.json exists."""
    assert not (INTEGRATION_ROOT / "strings.json").exists()

    en_raw = (INTEGRATION_ROOT / "translations" / "en.json").read_text(encoding="utf-8")
    es_raw = (INTEGRATION_ROOT / "translations" / "es.json").read_text(encoding="utf-8")

    assert "[%key:" not in en_raw
    assert "[%key:" not in es_raw

    en = json.loads(en_raw)
    es = json.loads(es_raw)
    assert _flatten_keys(en) == _flatten_keys(es)


def test_brand_assets_meet_hassfest_and_marketplace_rules() -> None:
    """Ensure brand icons satisfy Home Assistant / Marketplace dimension rules with no duplicates."""
    # No stray PNG files in the integration root outside brand/
    root_pngs = list(INTEGRATION_ROOT.glob("*.png"))
    assert root_pngs == []

    brand_dir = INTEGRATION_ROOT / "brand"
    expected = {
        "icon.png": (256, 256),
        "icon@2x.png": (512, 512),
    }
    present = {p.name for p in brand_dir.iterdir() if p.is_file()}
    assert present == set(expected.keys())

    for filename, expected_size in expected.items():
        path = brand_dir / filename
        assert _png_dimensions(path) == expected_size


def test_hacs_json_and_license_valid() -> None:
    """Verify hacs.json and LICENSE satisfy Marketplace / HACS requirements."""
    hacs = json.loads((REPO_ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["name"] == "Calidad del Aire - Gobierno de Canarias"
    assert hacs["country"] == ["ES"]
    assert hacs["homeassistant"] == "2025.8.0"
    assert hacs["hide_default_branch"] is True
    assert hacs["render_readme"] is True

    assert (REPO_ROOT / "LICENSE").is_file()
