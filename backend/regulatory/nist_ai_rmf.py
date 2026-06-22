"""NIST AI RMF — Function/category/subcategory control mappings per layer."""

LAYER_CONTROLS: dict[int, list[str]] = {
    1: ["GOVERN-1.1"],
    2: ["GOVERN-1.2", "GOVERN-1.4"],
    3: ["MANAGE-1.3"],
    4: ["MAP-1.1"],
    5: ["MEASURE-2.5"],
    6: ["MEASURE-2.2", "MANAGE-2.2"],
    7: ["GOVERN-6.1"],
}

KILL_SWITCH_CONTROLS: list[str] = ["MANAGE-1.3", "MANAGE-2.4"]
HUMAN_REVIEW_CONTROLS: list[str] = ["GOVERN-5.1"]

ALL_CONTROLS = [
    "GOVERN-1.1", "GOVERN-1.2", "GOVERN-1.4", "GOVERN-5.1", "GOVERN-6.1",
    "MAP-1.1",
    "MEASURE-2.2", "MEASURE-2.5",
    "MANAGE-1.3", "MANAGE-2.2", "MANAGE-2.4",
]
