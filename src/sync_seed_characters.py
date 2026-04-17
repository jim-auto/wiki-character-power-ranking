"""Synchronize the canonical seed list into data/characters.yaml."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


DEFAULT_SEED = Path("data/seed_characters.yaml")
DEFAULT_DATA = Path("data/characters.yaml")
VALID_MEDIA_TYPES = {"manga", "anime", "movie", "comic"}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            data,
            handle,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )


def validate_seed(seed: dict[str, Any]) -> None:
    seen_names: set[str] = set()
    seen_urls: set[str] = set()

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

        name = str(character["name"])
        url = str(character["wikipedia_url"])
        if name in seen_names:
            raise ValueError(f"Duplicate seed name: {name}")
        if url in seen_urls:
            raise ValueError(f"Duplicate seed URL: {url}")
        seen_names.add(name)
        seen_urls.add(url)


def sync_seed(seed: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_seed(seed)
    existing_by_url = {
        str(character.get("wikipedia_url")): character
        for character in (existing or {}).get("characters", [])
        if character.get("wikipedia_url")
    }

    characters: list[dict[str, Any]] = []
    for seed_character in seed["characters"]:
        url = str(seed_character["wikipedia_url"])
        character = dict(existing_by_url.get(url, {}))
        character.update(
            {
                "name": seed_character["name"],
                "wikipedia_url": url,
                "media_type": seed_character["media_type"],
                "universe": seed_character["universe"],
            }
        )
        character.setdefault("description_raw", "")
        characters.append(character)

    return {"characters": characters}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync seed characters into the main data file.")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--input", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATA)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    seed = load_yaml(args.seed)
    existing = load_yaml(args.input) if args.input.exists() else None
    save_yaml(args.output, sync_seed(seed, existing))


if __name__ == "__main__":
    main()
