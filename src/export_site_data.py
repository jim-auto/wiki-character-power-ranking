"""Export YAML character data for the GitHub Pages static app."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")
DEFAULT_OUTPUT = Path("docs/data/characters.json")
DETAIL_DIR_NAME = "character-details"
SUMMARY_SCORE_EVIDENCE_LIMIT = 1
SUMMARY_IQ_EVIDENCE_LIMIT = 3
SUMMARY_EXPLICIT_IQ_EVIDENCE_LIMIT = 2
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
    "explicit_iq",
    "explicit_iq_evidence",
    "estimated_iq",
    "condition_flags",
    "collection_tags",
    "image_url",
    "image_source",
    "image_alt",
    "image_landing_url",
    "image_creator",
    "image_creator_url",
    "image_license",
    "image_license_url",
    "image_credit",
    "versions",
]
VERSION_EXPORT_FIELDS = [
    "label",
    "aliases",
    "source_wikipedia_url",
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
]


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def selected_fields(source: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {key: source.get(key) for key in fields if key in source and key != "versions"}


def trim_score_evidence(evidence: Any, *, limit: int = SUMMARY_SCORE_EVIDENCE_LIMIT) -> dict[str, list[Any]]:
    if not isinstance(evidence, dict):
        return {}
    return {
        str(key): list(items[:limit])
        for key, items in evidence.items()
        if isinstance(items, list) and items[:limit]
    }


def trim_list(value: Any, *, limit: int) -> list[Any]:
    return list(value[:limit]) if isinstance(value, list) else []


def build_version_record(version: dict[str, Any], *, summary: bool) -> dict[str, Any]:
    record = selected_fields(version, VERSION_EXPORT_FIELDS)
    if summary:
        record["score_evidence"] = trim_score_evidence(record.get("score_evidence"))
        record["iq_evidence"] = trim_list(record.get("iq_evidence"), limit=SUMMARY_IQ_EVIDENCE_LIMIT)
        record["explicit_iq_evidence"] = trim_list(
            record.get("explicit_iq_evidence"),
            limit=SUMMARY_EXPLICIT_IQ_EVIDENCE_LIMIT,
        )
    return record


def build_character_record(character: dict[str, Any], *, summary: bool, detail_path: str | None = None) -> dict[str, Any]:
    record = selected_fields(character, EXPORT_FIELDS)
    versions = [
        build_version_record(version, summary=summary)
        for version in character.get("versions") or []
        if isinstance(version, dict)
    ]
    if versions:
        record["versions"] = versions
    if summary:
        record["score_evidence"] = trim_score_evidence(record.get("score_evidence"))
        record["iq_evidence"] = trim_list(record.get("iq_evidence"), limit=SUMMARY_IQ_EVIDENCE_LIMIT)
        record["explicit_iq_evidence"] = trim_list(
            record.get("explicit_iq_evidence"),
            limit=SUMMARY_EXPLICIT_IQ_EVIDENCE_LIMIT,
        )
        if detail_path:
            record["detail_path"] = detail_path
    return record


def reset_detail_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def export_json(input_path: Path, output_path: Path) -> None:
    data = load_yaml(input_path)
    records = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    detail_dir = output_path.parent / DETAIL_DIR_NAME
    reset_detail_dir(detail_dir)

    for index, character in enumerate(data["characters"], start=1):
        detail_filename = f"{index:03d}.json"
        detail_path = detail_dir / detail_filename
        detail_record = build_character_record(character, summary=False)
        detail_path.write_text(json_text(detail_record), encoding="utf-8")
        records.append(
            build_character_record(
                character,
                summary=True,
                detail_path=f"data/{DETAIL_DIR_NAME}/{detail_filename}",
            )
        )

    output_path.write_text(json_text(records), encoding="utf-8")


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
