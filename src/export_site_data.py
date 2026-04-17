"""Export YAML character data for the GitHub Pages static app."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")
DEFAULT_OUTPUT = Path("docs/data/characters.json")
EXPORT_FIELDS = [
    "name",
    "wikipedia_url",
    "media_type",
    "universe",
    "scores",
    "score_evidence",
    "total_score",
    "tier",
    "iq_score",
    "iq_evidence",
    "condition_flags",
    "collection_tags",
    "image_url",
    "image_source",
    "image_alt",
]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def export_json(input_path: Path, output_path: Path) -> None:
    data = load_yaml(input_path)
    records = [
        {key: character.get(key) for key in EXPORT_FIELDS if key in character}
        for character in data["characters"]
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export site JSON from YAML data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    export_json(args.input, args.output)


if __name__ == "__main__":
    main()
