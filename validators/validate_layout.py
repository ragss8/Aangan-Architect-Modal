"""Validate Architecture JSON and return machine-readable layout violations."""

from __future__ import annotations

import argparse
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "architecture.schema.json"
EPSILON = 1e-9


@lru_cache(maxsize=1)
def _schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _nonfinite_violations(value: Any, path: str = "$") -> list[dict[str, Any]]:
    if isinstance(value, float) and not math.isfinite(value):
        return [{"type": "SCHEMA_ERROR", "path": path, "message": f"{path}: number must be finite"}]
    if isinstance(value, dict):
        return [
            violation
            for key, item in value.items()
            for violation in _nonfinite_violations(item, f"{path}.{key}")
        ]
    if isinstance(value, list):
        return [
            violation
            for index, item in enumerate(value)
            for violation in _nonfinite_violations(item, f"{path}[{index}]")
        ]
    return []


def _overlap(first: dict[str, Any], second: dict[str, Any]) -> bool:
    x_overlap = min(first["x"] + first["width"], second["x"] + second["width"]) - max(first["x"], second["x"])
    y_overlap = min(first["y"] + first["depth"], second["y"] + second["depth"]) - max(first["y"], second["y"])
    return x_overlap > EPSILON and y_overlap > EPSILON


def _schema_violation(error: Any, layout: Any) -> dict[str, Any]:
    path = list(error.absolute_path)
    if (
        error.validator == "minimum"
        and len(path) == 5
        and path[0] == "floors"
        and path[2] == "rooms"
        and path[4] in {"x", "y"}
    ):
        floor = layout["floors"][path[1]]
        room = floor["rooms"][path[3]]
        edge = "west" if path[4] == "x" else "south"
        violation: dict[str, Any] = {
            "type": "PLOT_BOUNDARY",
            "path": error.json_path,
            "edge": edge,
            "message": f"{error.json_path}: extends beyond the {edge} plot edge",
        }
        if isinstance(floor.get("level"), int):
            violation["level"] = floor["level"]
        if isinstance(room.get("id"), str):
            violation["room"] = room["id"]
        return violation

    return {
        "type": "SCHEMA_ERROR",
        "path": error.json_path,
        "message": f"{error.json_path}: {error.message}",
    }


def validate_layout(layout: Any) -> dict[str, Any]:
    """Return {"valid": bool, "violations": [...]} for one layout.

    Geometry checks run after schema checks because they require complete numeric
    plot and room fields. Rooms on different floors may occupy the same footprint.
    """
    violations = _nonfinite_violations(layout)
    schema_errors = sorted(
        _schema_validator().iter_errors(layout),
        key=lambda error: (tuple(map(str, error.absolute_path)), error.message),
    )
    violations.extend(_schema_violation(error, layout) for error in schema_errors)
    if violations:
        return {"valid": False, "violations": violations}

    plot = layout["plot"]
    seen_levels: set[int] = set()
    seen_room_ids: set[str] = set()

    for floor in layout["floors"]:
        level = floor["level"]
        if level in seen_levels:
            violations.append({
                "type": "DUPLICATE_FLOOR_LEVEL",
                "level": level,
                "message": f"floor {level}: duplicate level",
            })
        seen_levels.add(level)

        rooms = floor["rooms"]
        for room in rooms:
            room_id = room["id"]
            if room_id in seen_room_ids:
                violations.append({
                    "type": "DUPLICATE_ROOM_ID",
                    "room": room_id,
                    "message": f"room {room_id}: duplicate id",
                })
            seen_room_ids.add(room_id)

            boundaries = (
                ("west", room["x"] < -EPSILON),
                ("south", room["y"] < -EPSILON),
                ("east", room["x"] + room["width"] > plot["width_ft"] + EPSILON),
                ("north", room["y"] + room["depth"] > plot["depth_ft"] + EPSILON),
            )
            for edge, outside in boundaries:
                if outside:
                    violations.append({
                        "type": "PLOT_BOUNDARY",
                        "level": level,
                        "room": room_id,
                        "edge": edge,
                        "message": f"floor {level}, room {room_id}: extends beyond the {edge} plot edge",
                    })

        for index, first in enumerate(rooms):
            for second in rooms[index + 1 :]:
                if _overlap(first, second):
                    violations.append({
                        "type": "ROOM_OVERLAP",
                        "level": level,
                        "rooms": [first["id"], second["id"]],
                        "message": f"floor {level}: rooms {first['id']} and {second['id']} overlap",
                    })

    return {"valid": not violations, "violations": violations}


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON number: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("architecture", type=Path, help="Architecture JSON file to validate")
    args = parser.parse_args()

    try:
        layout = json.loads(args.architecture.read_text(encoding="utf-8"), parse_constant=_reject_nonstandard_constant)
        result = validate_layout(layout)
    except (OSError, ValueError) as exc:
        result = {"valid": False, "violations": [{"type": "INVALID_JSON", "message": str(exc)}]}

    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
