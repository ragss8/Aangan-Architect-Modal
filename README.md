# Aangan-Architect-Modal

Training repository for the Aangan architect AI assistant.

## Architecture JSON (version 1)

[schemas/architecture.schema.json](schemas/architecture.schema.json) defines the model's output format. [schemas/architecture.example.json](schemas/architecture.example.json) is a valid example. Every output has a `plot` and a list of `floors`; each floor has a `level` and rectangular `rooms`.

All coordinates and room dimensions are in feet. The origin `(0, 0)` is the southwest corner of the plot. `x` increases east, and `y` increases north. `plot.width_ft` is the east-west size and `plot.depth_ft` is the south-north size, regardless of `facing`. `facing` identifies the road side; for example, an east-facing plot has its road on the `x = width_ft` edge.

Room IDs must be unique across the entire building. Floors must have distinct levels, and rooms on the same floor must fit within the plot without overlapping. Rooms may share an edge. [validators/validate_layout.py](validators/validate_layout.py) is the canonical validation API. It returns `{"valid": ..., "violations": [...]}` with codes such as `ROOM_OVERLAP` and `PLOT_BOUNDARY`. The existing [text validator](validators/validate_architecture.py) uses the same checks:

```bash
.venv/bin/python validators/validate_architecture.py schemas/architecture.example.json
.venv/bin/python -m validators.validate_layout schemas/architecture.example.json
```

```python
from validators.validate_layout import validate_layout

result = validate_layout(layout)
if not result["valid"]:
    print(result["violations"])
```

Validation version 1 checks the JSON Schema, finite and positive dimensions, plot boundaries, overlapping rooms on each floor, unique floor levels, and unique room IDs. The schema does not yet represent doors, corridors, stairs, windows, or other features needed for later checks.

The first version stores rectangles only. A later schema version can add polygons, openings, adjacency, and derived values such as area and Vastu zone without changing the meaning of the current fields.

## Starter Vastu checks

[rules/vastu.yaml](rules/vastu.yaml) contains the current placement preferences for `kitchen`, `master_bedroom`, `pooja`, and `living`. These are provisional project rules, not a complete Vastu knowledge base. [validators/check_vastu.py](validators/check_vastu.py) reads that file and evaluates each room only after the Architecture JSON passes structural and geometry validation.

The checker divides the plot into nine equal zones. It assigns each room to the zone containing its center point; a center exactly on a one-third boundary belongs to the middle band. It reports `preferred`, `alternative`, `non_preferred`, or `unruled` for each room. `unruled` means no rule exists yet for that room type; it does not mean the placement is approved.

```bash
.venv/bin/python -m validators.check_vastu schemas/architecture.example.json
.venv/bin/python -m validators.check_vastu --json schemas/architecture.example.json
```

Exit code `0` means no configured rule was violated, `1` means at least one room is `non_preferred`, and `2` means the input or rules could not be validated. Check the `unruled` count before treating a result as complete.

The Architecture JSON example deliberately places its living room in `SW`, so the Vastu checker reports `non_preferred` and exits with code `1` for that example.
