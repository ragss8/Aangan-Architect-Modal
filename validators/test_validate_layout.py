"""Behavior checks for structured layout validation."""

from __future__ import annotations

import copy
import json
import unittest

from validators.validate_layout import validate_layout


def overlapping_layout() -> dict:
    return {
        "plot": {"width_ft": 30, "depth_ft": 40, "facing": "east"},
        "floors": [{
            "level": 0,
            "rooms": [
                {"id": "bedroom_01", "type": "bedroom", "x": 2, "y": 5, "width": 15, "depth": 14},
                {"id": "kitchen_01", "type": "kitchen", "x": 10, "y": 8, "width": 10, "depth": 10},
            ],
        }],
    }


class ValidateLayoutTests(unittest.TestCase):
    def test_user_overlap_example_returns_room_ids(self) -> None:
        result = validate_layout(overlapping_layout())
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["violations"]), 1)
        self.assertEqual(result["violations"][0]["type"], "ROOM_OVERLAP")
        self.assertEqual(result["violations"][0]["rooms"], ["bedroom_01", "kitchen_01"])
        json.dumps(result)

    def test_room_beyond_plot_boundary(self) -> None:
        layout = overlapping_layout()
        layout["floors"][0]["rooms"][1]["x"] = 25
        result = validate_layout(layout)
        self.assertFalse(result["valid"])
        self.assertEqual(result["violations"][0]["type"], "PLOT_BOUNDARY")
        self.assertEqual(result["violations"][0]["edge"], "east")

    def test_negative_coordinate_reports_plot_boundary(self) -> None:
        layout = overlapping_layout()
        layout["floors"][0]["rooms"][0]["x"] = -1
        result = validate_layout(layout)
        self.assertFalse(result["valid"])
        self.assertEqual(result["violations"][0]["type"], "PLOT_BOUNDARY")
        self.assertEqual(result["violations"][0]["edge"], "west")

    def test_shared_edge_and_same_footprint_on_different_floors_are_allowed(self) -> None:
        layout = overlapping_layout()
        layout["floors"][0]["rooms"][1]["x"] = 17
        self.assertTrue(validate_layout(layout)["valid"])

        upper_room = copy.deepcopy(layout["floors"][0]["rooms"][0])
        upper_room["id"] = "bedroom_02"
        layout["floors"].append({"level": 1, "rooms": [upper_room]})
        self.assertTrue(validate_layout(layout)["valid"])

    def test_duplicate_room_id_is_rejected_across_floors(self) -> None:
        layout = overlapping_layout()
        layout["floors"][0]["rooms"][1]["x"] = 17
        layout["floors"].append({"level": 1, "rooms": [copy.deepcopy(layout["floors"][0]["rooms"][0])]})
        result = validate_layout(layout)
        self.assertEqual([item["type"] for item in result["violations"]], ["DUPLICATE_ROOM_ID"])

    def test_bad_shape_stops_geometry_checks(self) -> None:
        layout = overlapping_layout()
        layout["floors"][0]["rooms"][0]["width"] = 0
        result = validate_layout(layout)
        self.assertFalse(result["valid"])
        self.assertEqual({item["type"] for item in result["violations"]}, {"SCHEMA_ERROR"})


if __name__ == "__main__":
    unittest.main()
