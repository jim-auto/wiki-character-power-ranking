"""Derive filterable condition flags from Wikipedia-derived text."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")


CONDITION_PATTERNS: dict[str, list[str]] = {
    "superpower": [
        r"\bsuperpower(?:s)?\b",
        r"\bsuperhuman\b",
        r"\bmetahuman\b",
        r"\bmutant\b",
        r"\bpsychic\b",
        r"\btelepath(?:y|ic)?\b",
        r"\btelekinesis\b",
        r"\bsupernatural\b",
        r"\bpower(?:s|ed)?\b",
        r"\bability\b",
        r"\babilities\b",
        r"\bgod(?:s|like)?\b",
        r"超能力",
        r"超人的",
        r"能力",
        r"神",
    ],
    "modified": [
        r"\bcyborg\b",
        r"\bandroid\b",
        r"\brobot\b",
        r"\bsynthetic\b",
        r"\bartificial\b",
        r"\bexperiment(?:s|al|ed)?\b",
        r"\bgenetic(?:ally)?\b",
        r"\bengineered\b",
        r"\bmodified\b",
        r"\bmutation\b",
        r"\benhanced\b",
        r"改造",
        r"人工",
        r"強化",
        r"サイボーグ",
    ],
    "technology": [
        r"\btechnology\b",
        r"\btechnological\b",
        r"\bnanotechnology\b",
        r"\barmor\b",
        r"\barmour\b",
        r"\bsuit\b",
        r"\bmachine\b",
        r"\bdevice(?:s)?\b",
        r"\bgadget(?:s)?\b",
        r"\bcomputer\b",
        r"\bAI\b",
        r"技術",
        r"装甲",
        r"機械",
    ],
    "magic": [
        r"\bmagic(?:al)?\b",
        r"\bspell(?:s)?\b",
        r"\bwizard\b",
        r"\bwitch\b",
        r"\bsorcer(?:er|ess|y)\b",
        r"\bmystic(?:al)?\b",
        r"\boccult\b",
        r"\bcurse(?:d|s)?\b",
        r"\bdemon(?:ic)?\b",
        r"魔法",
        r"呪",
        r"妖",
    ],
    "weapon": [
        r"\bweapon(?:s)?\b",
        r"\bsword(?:s)?\b",
        r"\bgun(?:s)?\b",
        r"\bfirearm(?:s)?\b",
        r"\bmissile(?:s)?\b",
        r"\blaser(?:s)?\b",
        r"\blightsaber(?:s)?\b",
        r"\bshield(?:s)?\b",
        r"\bhammer\b",
        r"\bprojectile(?:s)?\b",
        r"武器",
        r"剣",
        r"銃",
        r"兵器",
    ],
}


COMPILED_PATTERNS = {
    key: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for key, patterns in CONDITION_PATTERNS.items()
}


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


def evidence_text(character: dict[str, Any]) -> str:
    parts: list[str] = [str(character.get("description_raw") or "")]
    extracted = character.get("extracted") or {}
    for values in extracted.values():
        if isinstance(values, list):
            parts.extend(str(value) for value in values)
    return "\n".join(parts)


def matched_patterns(text: str, regexes: Iterable[re.Pattern[str]]) -> list[str]:
    matches: list[str] = []
    for regex in regexes:
        match = regex.search(text)
        if match:
            matches.append(match.group(0))
    return matches


def derive_condition_flags(character: dict[str, Any]) -> dict[str, bool]:
    text = evidence_text(character)
    return {
        key: bool(matched_patterns(text, regexes))
        for key, regexes in COMPILED_PATTERNS.items()
    }


def derive_condition_evidence(character: dict[str, Any]) -> dict[str, list[str]]:
    text = evidence_text(character)
    return {
        key: matched_patterns(text, regexes)[:5]
        for key, regexes in COMPILED_PATTERNS.items()
    }


def update_characters(data: dict[str, Any]) -> dict[str, Any]:
    for character in data["characters"]:
        character["condition_flags"] = derive_condition_flags(character)
        character["condition_evidence"] = derive_condition_evidence(character)
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Derive condition flags for static filtering."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    save_yaml(args.output, update_characters(data))


if __name__ == "__main__":
    main()
