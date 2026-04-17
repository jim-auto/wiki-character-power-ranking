"""Attach display/search collection tags to character records."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")

JUMP_MANGA_UNIVERSES = {
    "Bleach",
    "Chainsaw Man",
    "Death Note",
    "Demon Slayer",
    "Dragon Ball",
    "Fist of the North Star",
    "Hunter x Hunter",
    "JoJo's Bizarre Adventure",
    "Jujutsu Kaisen",
    "My Hero Academia",
    "Naruto",
    "One Piece",
    "One-Punch Man",
    "Rurouni Kenshin",
    "Tokyo Ghoul",
    "Yu-Gi-Oh!",
    "YuYu Hakusho",
}


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
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False, width=1000)
    temp_path.replace(path)


def update_characters(data: dict[str, Any]) -> dict[str, Any]:
    for character in data["characters"]:
        tags: list[str] = []
        universe = str(character.get("universe") or "")
        media_type = str(character.get("media_type") or "")

        if universe in JUMP_MANGA_UNIVERSES and media_type in {"manga", "anime"}:
            tags.append("jump_manga")

        if universe in {"Marvel", "MCU"}:
            tags.append("marvel")
        if universe in {"DC", "DCEU", "Dark Knight Trilogy"}:
            tags.append("dc")

        character["collection_tags"] = tags
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attach collection tags for site filters.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    save_yaml(args.output, update_characters(data))


if __name__ == "__main__":
    main()
