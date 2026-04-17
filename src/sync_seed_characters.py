"""Synchronize the canonical seed list into data/characters.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


DEFAULT_SEED = Path("data/seed_characters.yaml")
DEFAULT_DATA = Path("data/characters.yaml")
VALID_MEDIA_TYPES = {"manga", "anime", "movie", "comic"}
SEED_OPTIONAL_KEYS = ["versions"]
DERIVED_KEYS = [
    "description_raw",
    "source_metadata",
    "extracted",
    "scores",
    "score_evidence",
    "total_score",
    "tier",
    "iq_score",
    "iq_evidence",
    "explicit_iq",
    "explicit_iq_evidence",
    "estimated_iq",
    "condition_flags",
    "condition_evidence",
    "collection_tags",
    "image_url",
    "image_source",
    "image_alt",
    "image_pageimage",
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            data,
            handle,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
    temp_path.replace(path)


def validate_seed(seed: dict[str, Any]) -> None:
    seen_names: set[str] = set()

    for index, character in enumerate(seed["characters"], start=1):
        missing = [
            key
            for key in ("name", "wikipedia_url", "media_type", "universe")
            if not character.get(key)
        ]
        if missing:
            raise ValueError(f"Seed row {index} is missing fields: {', '.join(missing)}")

        media_type = character["media_type"]
        if media_type not in VALID_MEDIA_TYPES:
            raise ValueError(f"Invalid media_type at row {index}: {media_type}")

        versions = character.get("versions") or []
        if not isinstance(versions, list):
            raise ValueError(f"Invalid versions at row {index}: expected list")
        seen_version_labels: set[str] = set()
        for version_index, version in enumerate(versions, start=1):
            if not isinstance(version, dict):
                raise ValueError(f"Invalid version at row {index}.{version_index}: expected mapping")
            label = str(version.get("label") or "").strip()
            if not label:
                raise ValueError(f"Version at row {index}.{version_index} is missing label")
            if label in seen_version_labels:
                raise ValueError(f"Duplicate version label at row {index}: {label}")
            seen_version_labels.add(label)
            if not str(version.get("description_raw") or "").strip():
                raise ValueError(f"Version at row {index}.{version_index} is missing description_raw")

        name = str(character["name"])
        url = str(character["wikipedia_url"])
        if name in seen_names:
            raise ValueError(f"Duplicate seed name: {name}")
        seen_names.add(name)


def sync_seed(seed: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_seed(seed)
    existing_by_name = {
        str(character.get("name")): character
        for character in (existing or {}).get("characters", [])
        if character.get("name")
    }
    urls: dict[str, list[dict[str, Any]]] = {}
    for character in (existing or {}).get("characters", []):
        if character.get("wikipedia_url"):
            urls.setdefault(str(character["wikipedia_url"]), []).append(character)
    existing_by_unique_url = {
        url: characters[0] for url, characters in urls.items() if len(characters) == 1
    }

    characters: list[dict[str, Any]] = []
    for seed_character in seed["characters"]:
        url = str(seed_character["wikipedia_url"])
        lookup_names = [
            str(seed_character["name"]),
            str(seed_character.get("source_name_original") or ""),
        ]
        existing_character = next(
            (existing_by_name[name] for name in lookup_names if name and name in existing_by_name),
            existing_by_unique_url.get(url, {}),
        )
        old_url = str(existing_character.get("wikipedia_url") or "")
        character = dict(existing_character)
        if old_url and old_url != url:
            for key in DERIVED_KEYS:
                character.pop(key, None)
        character.update(
            {
                "name": seed_character["name"],
                "wikipedia_url": url,
                "media_type": seed_character["media_type"],
                "universe": seed_character["universe"],
            }
        )
        for key, value in seed_character.items():
            if key.startswith("source_"):
                character[key] = value
        for key in SEED_OPTIONAL_KEYS:
            if key in seed_character:
                character[key] = seed_character[key]
            else:
                character.pop(key, None)
        character.setdefault("description_raw", "")
        characters.append(character)

    return {"characters": characters}


def clear_derived_fields(data: dict[str, Any]) -> dict[str, Any]:
    for character in data["characters"]:
        for key in DERIVED_KEYS:
            character.pop(key, None)
        character["description_raw"] = ""
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync seed characters into the main data file.")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATA)
    parser.add_argument(
        "--reset-derived",
        action="store_true",
        help="Clear fetched text, scores, evidence, and generated flags after syncing.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    seed = load_yaml(args.seed)
    existing = load_yaml(args.input) if args.input.exists() else None
    synced = sync_seed(seed, existing)
    if args.reset_derived:
        synced = clear_derived_fields(synced)
    save_yaml(args.output, synced)


if __name__ == "__main__":
    main()
