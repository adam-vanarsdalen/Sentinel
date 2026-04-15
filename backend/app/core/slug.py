from __future__ import annotations

import re

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def slugify_name(name: str) -> str:
    return normalize_slug(name)


def validate_slug(slug: str) -> None:
    if not slug or not SLUG_RE.fullmatch(slug):
        raise ValueError("Invalid slug. Expected: [a-z0-9]+(?:-[a-z0-9]+)*")

