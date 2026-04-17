"""Extract strength-related evidence sentences from Wikipedia text."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")


ABILITY_PATTERNS = [
    r"\babilit(?:y|ies)\b",
    r"\bable to\b",
    r"\bcapable of\b",
    r"\bcan\b",
    r"\btechnique(?:s)?\b",
    r"\bmartial arts?\b",
    r"\bfighting skills?\b",
    r"\bdetective abilities\b",
    r"\bdetective\b",
    r"\bgenius\b",
    r"\bintellect\b",
    r"\bintellectual(?:ly)?\b",
    r"\bscience and technology\b",
    r"\bscience\b",
    r"\btechnology\b",
    r"\bstrateg(?:y|ist|ic|ical)\b",
    r"\btactic(?:s|al)?\b",
    r"\binvent(?:or|s|ed|ion)?\b",
    r"\bindustrialist\b",
    r"\bweapon(?:s)?\b",
    r"\bpowered exoskeletons?\b",
    r"\bnanotechnology\b",
    r"\bsuperhuman\b",
    r"\bchakra\b",
    r"\bninja\b",
    r"\bjutsu\b",
    r"\bshadow clone\b",
    r"\brasengan\b",
    r"\bkamehameha\b",
    r"\bsuper saiyan\b",
    r"\bteleportation\b",
    r"\bflight\b",
    r"能力",
    r"技",
    r"忍術",
    r"武器",
    r"兵器",
    r"超人的",
    r"天才",
    r"知能",
    r"知性",
    r"知的",
    r"科学",
    r"技術",
    r"発明",
    r"戦略",
    r"戦術",
    r"探偵",
    r"熟練",
    r"変身",
    r"飛行",
    r"瞬間移動",
]

FEAT_PATTERNS = [
    r"\bdefeat(?:s|ed|ing)?\b",
    r"\bbattle(?:s|d|ing)?\b",
    r"\bfight(?:s|ed)?\b",
    r"\bprotect(?:s|ed|ing)?\b",
    r"\bsav(?:e|es|ed|ing)\b",
    r"\bwin(?:s|ning)?\b",
    r"\bvictor(?:y|ies|ious)?\b",
    r"\boperates in\b",
    r"倒",
    r"勝利",
    r"戦績",
    r"戦う",
    r"戦い",
    r"守る",
    r"救",
]

STATEMENT_PATTERNS = [
    r"\bmightiest\b",
    r"\bpowerful\b",
    r"\bstrong(?:er|est)?\b",
    r"\bindomitable\b",
    r"\bunstoppable\b",
    r"\binvincible\b",
    r"\bgod(?:like)?\b",
    r"\bno inherent superhuman powers\b",
    r"最強",
    r"強力",
    r"圧倒",
    r"無敵",
    r"神のよう",
]

RELEVANCE_PATTERNS = ABILITY_PATTERNS + FEAT_PATTERNS + STATEMENT_PATTERNS + [
    r"\barmor\b",
    r"\bdurability\b",
    r"\bstrength\b",
    r"\bspeed\b",
    r"\bmissile(?:s)?\b",
    r"\blaser(?:s)?\b",
    r"\brepulsor(?:s)?\b",
    r"\bplanet\b",
    r"\bearth\b",
    r"\bworld\b",
    r"\bcity\b",
    r"\bvillage\b",
    r"装甲",
    r"耐久",
    r"速度",
    r"都市",
    r"国家",
    r"惑星",
    r"地球",
    r"宇宙",
    r"世界",
    r"村",
]


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


def compile_patterns(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


ABILITY_REGEXES = compile_patterns(ABILITY_PATTERNS)
FEAT_REGEXES = compile_patterns(FEAT_PATTERNS)
STATEMENT_REGEXES = compile_patterns(STATEMENT_PATTERNS)
RELEVANCE_REGEXES = compile_patterns(RELEVANCE_PATTERNS)


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.replace("\r", "\n")).strip()
    if not normalized:
        return []

    pieces = re.split(r"(?<=[.!?。！？])\s+", normalized)
    return [piece.strip() for piece in pieces if piece.strip()]


def matches_any(sentence: str, regexes: Iterable[re.Pattern[str]]) -> bool:
    return any(regex.search(sentence) for regex in regexes)


def append_unique(target: list[str], sentence: str) -> None:
    if sentence not in target:
        target.append(sentence)


def extract_from_text(text: str) -> dict[str, list[str]]:
    extracted: dict[str, list[str]] = {
        "abilities": [],
        "feats": [],
        "statements": [],
    }

    for sentence in split_sentences(text):
        if not matches_any(sentence, RELEVANCE_REGEXES):
            continue

        classified = False
        if matches_any(sentence, ABILITY_REGEXES):
            append_unique(extracted["abilities"], sentence)
            classified = True
        if matches_any(sentence, FEAT_REGEXES):
            append_unique(extracted["feats"], sentence)
            classified = True
        if matches_any(sentence, STATEMENT_REGEXES):
            append_unique(extracted["statements"], sentence)
            classified = True

        if not classified:
            append_unique(extracted["statements"], sentence)

    return extracted


def update_characters(data: dict[str, Any]) -> dict[str, Any]:
    for character in data["characters"]:
        text = character.get("description_raw") or ""
        character["extracted"] = extract_from_text(text)
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract ability, feat, and statement evidence from Wikipedia text."
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
