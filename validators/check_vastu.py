"""Check Architecture JSON room locations against the configured Vastu rules."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from validators.validate_architecture import validate_architecture


RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "vastu.yaml"
ZONES = frozenset({"NW", "N", "NE", "W", "C", "E", "SW", "S", "SE"})
ZONE_GRID = (("SW", "S", "SE"), ("W", "C", "E"), ("NW", "N", "NE"))
ROOM_TYPE_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")


def _zone_list(value: Any, room_type: str, field: str, *, required: bool) -> list[str]:
    if not isinstance(value, list) or (required and not value):
        raise ValueError(f"{room_type}.{field} must be a {'nonempty ' if required else ''}list")
    if any(not isinstance(zone, str) or zone not in ZONES for zone in value):
        raise ValueError(f"{room_type}.{field} contains an unknown zone")
    if len(value) != len(set(value)):
        raise ValueError(f"{room_type}.{field} contains duplicate zones")
    return value


def load_rules(path: Path = RULES_PATH) -> dict[str, dict[str, list[str]]]:
    """Load and validate the project's Vastu rule configuration."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Vastu rules must be a nonempty mapping of room types")

    rules: dict[str, dict[str, list[str]]] = {}
    for room_type, rule in raw.items():
        if not isinstance(room_type, str) or not ROOM_TYPE_PATTERN.fullmatch(room_type):
            raise ValueError(f"invalid room type in Vastu rules: {room_type!r}")
        if not isinstance(rule, dict) or set(rule) - {"preferred", "alternatives"}:
            raise ValueError(f"{room_type} must contain only preferred and alternatives")
        if "preferred" not in rule:
            raise ValueError(f"{room_type} requires preferred zones")

        preferred = _zone_list(rule["preferred"], room_type, "preferred", required=True)
        alternatives = _zone_list(rule.get("alternatives", []), room_type, "alternatives", required=False)
        if set(preferred) & set(alternatives):
            raise ValueError(f"{room_type} repeats a zone across preferred and alternatives")
        rules[room_type] = {"preferred": preferred, "alternatives": alternatives}

    return rules


def _band(position: float, extent: float) -> int:
    if position < extent / 3:
        return 0
    if position > 2 * extent / 3:
        return 2
    return 1


def room_zone(room: dict[str, Any], plot: dict[str, Any]) -> str:
    """Locate a rectangular room by its center in the plot's nine-zone grid."""
    center_x = room["x"] + room["width"] / 2
    center_y = room["y"] + room["depth"] / 2
    return ZONE_GRID[_band(center_y, plot["depth_ft"])][_band(center_x, plot["width_ft"])]


def evaluate_vastu(document: Any, rules: dict[str, dict[str, list[str]]]) -> list[dict[str, Any]]:
    """Return a finding for every room; reject invalid Architecture JSON."""
    errors = validate_architecture(document)
    if errors:
        raise ValueError("invalid Architecture JSON: " + "; ".join(errors))

    findings = []
    for floor in document["floors"]:
        for room in floor["rooms"]:
            zone = room_zone(room, document["plot"])
            rule = rules.get(room["type"])
            if rule is None:
                status = "unruled"
            elif zone in rule["preferred"]:
                status = "preferred"
            elif zone in rule["alternatives"]:
                status = "alternative"
            else:
                status = "non_preferred"

            findings.append({
                "level": floor["level"],
                "room_id": room["id"],
                "room_type": room["type"],
                "zone": zone,
                "status": status,
            })
    return findings


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON number: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("architecture", type=Path, help="Architecture JSON file to check")
    parser.add_argument("--rules", type=Path, default=RULES_PATH, help="Vastu YAML rules file")
    parser.add_argument("--json", action="store_true", help="print machine-readable findings")
    args = parser.parse_args()

    try:
        document = json.loads(args.architecture.read_text(encoding="utf-8"), parse_constant=_reject_nonstandard_constant)
        findings = evaluate_vastu(document, load_rules(args.rules))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"Vastu check failed: {exc}", file=sys.stderr)
        return 2

    counts = {status: sum(item["status"] == status for item in findings) for status in ("preferred", "alternative", "non_preferred", "unruled")}
    if args.json:
        print(json.dumps({"findings": findings, "counts": counts}, indent=2))
    else:
        for item in findings:
            print(f"floor {item['level']}, {item['room_id']} ({item['room_type']}): {item['zone']} — {item['status']}")
        print(", ".join(f"{count} {status}" for status, count in counts.items()))

    return 1 if counts["non_preferred"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
