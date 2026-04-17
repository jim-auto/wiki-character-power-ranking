"""Deterministic text-only scoring for character power records."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")
SCORE_KEYS = ["attack", "defense", "speed", "abilities", "feats", "scale"]
IQ_SCORE_KEY = "iq"


@dataclass(frozen=True)
class Rule:
    pattern: str
    points: int
    label: str

    def regex(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.IGNORECASE)


RULES: dict[str, list[Rule]] = {
    "attack": [
        Rule(r"\bmightiest\b|\bstrongest\b|最強", 5, "strong expression: mightiest/strongest"),
        Rule(r"\bdestroy(?:s|ed|ing)?\b|\bannihilat(?:e|es|ed|ing)\b|破壊", 5, "destruction expression"),
        Rule(r"\benergy wave\b|\bbeam\b|\blaser(?:s)?\b|\bkamehameha\b|ビーム", 4, "energy attack expression"),
        Rule(r"\bmissile(?:s)?\b|\brepulsor(?:s)?\b|\bweapon(?:s)?\b|\boffensive systems?\b|武器|兵器", 4, "weapon expression"),
        Rule(r"\brasengan\b|\battack(?:s)?\b|攻撃", 4, "attack technique expression"),
        Rule(r"\bfighting skills?\b|\bmartial arts?\b|格闘|武術", 3, "combat skill expression"),
        Rule(r"\bbattle(?:s|d|ing)?\b|\bfight(?:s|ing)?\b|戦", 2, "battle/fight expression"),
    ],
    "defense": [
        Rule(r"\binvincible\b|\binvulnerab(?:le|ility)\b|無敵", 7, "invulnerability expression"),
        Rule(r"\bdurability\b|\bdurable\b|耐久", 4, "durability expression"),
        Rule(r"\barmor\b|\barmour\b|\bexoskeleton(?:s)?\b|装甲", 3, "armor expression"),
        Rule(r"\bshield(?:s|ed|ing)?\b|シールド", 3, "shield expression"),
        Rule(r"\bsealed within\b|\bcontain(?:s|ed|ing)?\b|封印", 3, "containment expression"),
        Rule(r"\bprotect(?:s|ed|ing)?\b|\bdefend(?:s|ed|ing)?\b|守", 2, "protection expression"),
        Rule(r"\bindomitable will\b|不屈", 2, "resilience expression"),
    ],
    "speed": [
        Rule(r"\bteleport(?:s|ed|ing|ation)?\b|瞬間移動", 5, "teleportation expression"),
        Rule(r"\bsuperhuman speed\b|超高速", 5, "superhuman speed expression"),
        Rule(r"\bflight\b|\bfly\b|\bflies\b|飛行", 4, "flight expression"),
        Rule(r"\bfast\b|\bspeed\b|\bquick\b|速度|高速", 3, "speed expression"),
    ],
    "abilities": [
        Rule(r"\bsuperhuman\b|超人的", 5, "superhuman expression"),
        Rule(r"\bdemon fox\b|\bnine-tailed\b|九尾", 5, "sealed entity expression"),
        Rule(r"\btechnique(?:s)?\b|\bjutsu\b|\brasengan\b|\bkamehameha\b|技|忍術", 4, "technique expression"),
        Rule(r"\bnanotechnology\b|ナノテク", 4, "technology expression"),
        Rule(r"\bcapable of\b|\bable to\b|\bcan\b|能力", 3, "capability expression"),
        Rule(r"\bpowered exoskeleton(?:s)?\b|\bweapon(?:s)?\b|装備|武器", 3, "equipment expression"),
        Rule(r"\bgenius\b|\bintellect\b|\bdetective abilities\b|\bscience and technology\b|天才|知性|探偵", 3, "intellect/skill expression"),
        Rule(r"\bmartial arts?\b|\bfighting skills?\b|\btrained\b|\btrains himself\b|熟練|訓練", 2, "training/skill expression"),
        Rule(r"\bninja\b|忍者", 2, "role expression"),
        Rule(r"\bbecomes\b|\btransform(?:s|ed|ing)?\b|変身", 3, "transformation expression"),
    ],
    "feats": [
        Rule(r"\bdefeat(?:s|ed|ing)?\b|\bwin(?:s|ning)?\b|\bvictor(?:y|ies|ious)?\b|倒|勝利", 5, "victory expression"),
        Rule(r"\bprotect(?:s|ed|ing)?\b|\bsav(?:e|es|ed|ing)\b|守|救", 3, "protection/saving feat"),
        Rule(r"\bbattle(?:s|d|ing)?\b|\bfight(?:s|ed)?\b|戦", 3, "battle feat"),
        Rule(r"\boperates in\b", 2, "active operation feat"),
    ],
    "scale": [
        Rule(r"\b(?:the|entire|whole|all of the)\s+universe\b|\bcosmic\b|\bdimension(?:s|al)?\b|宇宙|次元", 9, "scale expression: universe/dimension"),
        Rule(r"\bplanet(?:s|ary)?\b|\bearth\b|惑星|地球", 7, "scale expression: planet/Earth"),
        Rule(r"\bworld\b|世界", 6, "scale expression: world"),
        Rule(r"\bnation\b|\bcountry\b|国家|国", 5, "scale expression: nation/country"),
        Rule(r"\bvillage\b|村", 3, "scale expression: village"),
        Rule(r"\bcity\b|都市", 2, "scale expression: city"),
    ],
    "iq": [
        Rule(r"\bgenius\b|天才", 5, "intelligence expression: genius"),
        Rule(r"\binvent(?:or|s|ed|ion)?\b|\bengineer(?:s|ed|ing)?\b|\bscientist\b|発明|科学者", 4, "invention/science expression"),
        Rule(r"\bstrateg(?:y|ist|ic|ical)\b|\btactic(?:s|al)?\b|戦略|戦術", 4, "strategy/tactics expression"),
        Rule(r"\bdetective abilities\b|\bdetective\b|探偵", 3, "detective expression"),
        Rule(r"\bintellect\b|\bintellectual(?:ly)?\b|知性|知能|知的", 3, "intellect expression"),
        Rule(r"\bscience and technology\b|\btechnology\b|\bnanotechnology\b|科学|技術|ナノテク", 3, "science/technology expression"),
        Rule(r"\bleader\b|\bhokage\b|指導者|リーダー", 2, "leadership expression"),
        Rule(r"\btrained\b|\btrains himself\b|訓練", 1, "training expression"),
    ],
}


COMPILED_RULES: dict[str, list[tuple[Rule, re.Pattern[str]]]] = {
    key: [(rule, rule.regex()) for rule in rules] for key, rules in RULES.items()
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


def evidence_sentences(character: dict[str, Any]) -> list[str]:
    extracted = character.get("extracted") or {}
    sentences: list[str] = []

    for key in ("abilities", "feats", "statements"):
        values = extracted.get(key) or []
        if isinstance(values, list):
            for sentence in values:
                if isinstance(sentence, str) and sentence not in sentences:
                    sentences.append(sentence)

    if not sentences:
        raw = character.get("description_raw") or ""
        sentences = [raw] if raw else []

    return sentences


def is_negated_hit(sentence: str, rule: Rule, dimension: str) -> bool:
    lower_sentence = sentence.casefold()
    if dimension == "abilities" and "superhuman" in rule.pattern:
        negated_phrases = [
            "no inherent superhuman powers",
            "no superhuman powers",
            "without superhuman powers",
        ]
        return any(phrase in lower_sentence for phrase in negated_phrases)
    return False


def score_dimension(
    sentences: Iterable[str],
    dimension: str,
) -> tuple[int, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    seen_hits: set[tuple[str, str]] = set()

    for sentence in sentences:
        for rule, regex in COMPILED_RULES[dimension]:
            if not regex.search(sentence):
                continue
            if is_negated_hit(sentence, rule, dimension):
                continue
            hit_key = (sentence, rule.label)
            if hit_key in seen_hits:
                continue
            seen_hits.add(hit_key)
            evidence.append(
                {
                    "sentence": sentence,
                    "rule": rule.label,
                    "points": rule.points,
                }
            )

    evidence.sort(key=lambda item: (-int(item["points"]), item["sentence"]))
    if dimension == "scale":
        score = max((int(item["points"]) for item in evidence), default=0)
    else:
        score = min(10, sum(int(item["points"]) for item in evidence))
    return score, evidence


def calculate_tier(total_score: int) -> str:
    if total_score >= 42:
        return "S"
    if total_score >= 30:
        return "A"
    if total_score >= 18:
        return "B"
    return "C"


def score_character(character: dict[str, Any]) -> dict[str, Any]:
    sentences = evidence_sentences(character)
    scores: dict[str, int] = {}
    score_evidence: dict[str, list[dict[str, Any]]] = {}

    for dimension in SCORE_KEYS:
        score, evidence = score_dimension(sentences, dimension)
        scores[dimension] = score
        score_evidence[dimension] = evidence

    iq_score, iq_evidence = score_dimension(sentences, IQ_SCORE_KEY)
    total_score = sum(scores.values())
    character["scores"] = scores
    character["score_evidence"] = score_evidence
    character["iq_score"] = iq_score
    character["iq_evidence"] = iq_evidence
    character["total_score"] = total_score
    character["tier"] = calculate_tier(total_score)
    return character


def update_characters(data: dict[str, Any]) -> dict[str, Any]:
    for character in data["characters"]:
        score_character(character)
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score character records using deterministic text rules."
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
