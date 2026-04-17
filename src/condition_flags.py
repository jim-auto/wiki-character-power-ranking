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
        r"\bpower(?:s)?\b",
        r"\bspecial abilit(?:y|ies)\b",
        r"\bextraordinary abilit(?:y|ies)\b",
        r"\benergy manipulation\b",
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
        r"\baugmented\b",
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
        r"\bartificial intelligence\b",
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
        r"\bdevil\b",
        r"\bangel\b",
        r"\bmonster\b",
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
        r"\barmor(?:y)?\b",
    ],
    "non_human": [
        r"\balien\b",
        r"\bextraterrestrial\b",
        r"\bdeity\b",
        r"\bgod(?:dess)?\b",
        r"\bdemon\b",
        r"\bdevil\b",
        r"\bmonster\b",
        r"\bvampire\b",
        r"\bwerewolf\b",
        r"\bmutant\b",
        r"\bandroid\b",
        r"\brobot\b",
        r"\bcyborg\b",
        r"\bspirit\b",
        r"\bghost\b",
        r"\bcreature\b",
    ],
    "god_or_deity": [
        r"\bdeity\b",
        r"\bgod(?:dess)?\b",
        r"\bdivine\b",
        r"\basgardian\b",
        r"\bolympian\b",
        r"\bnew god\b",
        r"\bcelestial\b",
    ],
    "alien": [
        r"\balien\b",
        r"\bextraterrestrial\b",
        r"\bfrom (?:the planet|planet)\b",
        r"\bkrypton(?:ian)?\b",
        r"\bsaiyan\b",
        r"\basgardian\b",
        r"\bmartian\b",
    ],
    "robot_ai": [
        r"\brobot\b",
        r"\bandroid\b",
        r"\bcyborg\b",
        r"\bAI\b",
        r"\bartificial intelligence\b",
        r"\bautomaton\b",
        r"\bsynthezoid\b",
    ],
    "martial_artist": [
        r"\bmartial artist\b",
        r"\bmartial arts?\b",
        r"\bkung fu\b",
        r"\bkarate\b",
        r"\bninja\b",
        r"\bsamurai\b",
        r"\bhand-to-hand\b",
        r"\bcombat skills?\b",
        r"\bfighting skills?\b",
    ],
    "military": [
        r"\bsoldier\b",
        r"\bmilitary\b",
        r"\barmy\b",
        r"\bmarine\b",
        r"\bassassin\b",
        r"\bmercenary\b",
        r"\bspy\b",
        r"\bagent\b",
        r"\bcommando\b",
        r"\bwarrior\b",
    ],
    "leader": [
        r"\bleader\b",
        r"\bking\b",
        r"\bqueen\b",
        r"\bprince\b",
        r"\bprincess\b",
        r"\bcommander\b",
        r"\bcaptain\b",
        r"\bruler\b",
        r"\bemperor\b",
        r"\bpresident\b",
        r"\bchief\b",
        r"\bhokage\b",
    ],
    "detective_genius": [
        r"\bgenius\b",
        r"\bintellect\b",
        r"\bintellectual\b",
        r"\bscientist\b",
        r"\binventor\b",
        r"\bengineer\b",
        r"\bdetective\b",
        r"\bstrategist\b",
        r"\btactician\b",
        r"\bmastermind\b",
    ],
    "transformation": [
        r"\btransform(?:s|ed|ing|ation)?\b",
        r"\bshape[- ]?shift(?:s|ed|ing|er)?\b",
        r"\bmetamorph(?:osis|ose)\b",
        r"\balter ego\b",
        r"\bform\b",
        r"\bpowered[- ]?up\b",
    ],
    "immortal": [
        r"\bimmortal(?:ity)?\b",
        r"\binvulnerab(?:le|ility)\b",
        r"\bregenerat(?:e|es|ed|ion|ive)\b",
        r"\bresurrect(?:s|ed|ion)?\b",
        r"\bundead\b",
        r"\bnearly impervious\b",
        r"\bhealing factor\b",
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
