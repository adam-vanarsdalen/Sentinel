"""HIPAA — Clause-level control mappings per layer."""

LAYER_CONTROLS: dict[int, list[str]] = {
    1: ["164.312(b)"],
    3: ["164.308(a)(3)"],
    7: ["164.312(b)"],
}

ALL_CONTROLS = [
    "164.308(a)(3)",
    "164.312(b)",
]
