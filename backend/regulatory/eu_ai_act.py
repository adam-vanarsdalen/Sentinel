"""EU AI Act — Article-level control mappings per layer."""

LAYER_CONTROLS: dict[int, list[str]] = {
    1: ["Article 12"],
    2: ["Article 9"],
    3: ["Article 14"],
    4: ["Article 13"],
    5: ["Article 15"],
    6: ["Article 9"],
    7: ["Article 11", "Article 12"],
}

KILL_SWITCH_CONTROLS: list[str] = ["Article 14"]
HUMAN_REVIEW_CONTROLS: list[str] = ["Article 14"]

ALL_ARTICLES = ["Article 9", "Article 11", "Article 12", "Article 13", "Article 14", "Article 15"]
