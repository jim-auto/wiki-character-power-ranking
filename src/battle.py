"""Compare two characters using Wikipedia-grounded scores only."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")
SCORE_KEYS = ["attack", "defense", "speed", "abilities", "feats", "scale"]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def find_character(characters: list[dict[str, Any]], query: str) -> dict[str, Any]:
    normalized = query.casefold()

    for character in characters:
        if str(character.get("name", "")).casefold() == normalized:
            return character

    matches = [
        character
        for character in characters
        if normalized in str(character.get("name", "")).casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(str(character.get("name", "")) for character in matches)
        raise ValueError(f"Ambiguous character query '{query}'. Matches: {names}")
    raise ValueError(f"Character not found: {query}")


def mode_score(character: dict[str, Any], mode: str) -> int:
    if mode == "iq":
        return int(character.get("iq_score", 0))
    if mode == "balanced":
        return int(character.get("total_score", 0)) + int(character.get("iq_score", 0))
    return int(character.get("total_score", 0))


def verdict(a: dict[str, Any], b: dict[str, Any], mode: str) -> str:
    a_score = mode_score(a, mode)
    b_score = mode_score(b, mode)
    diff = a_score - b_score

    if diff == 0:
        return "Draw by current Wikipedia-grounded scores."

    winner = a if diff > 0 else b
    margin = abs(diff)
    strength = "favored" if margin >= 8 else "slight edge"
    return f"{winner.get('name')} is {strength} in {mode} mode by {margin} point(s)."


def dimension_table(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    a_scores = a.get("scores") or {}
    b_scores = b.get("scores") or {}
    lines = ["| Dimension | A | B | Edge |", "| --- | ---: | ---: | --- |"]

    for key in SCORE_KEYS:
        a_value = int(a_scores.get(key, 0))
        b_value = int(b_scores.get(key, 0))
        if a_value > b_value:
            edge = str(a.get("name"))
        elif b_value > a_value:
            edge = str(b.get("name"))
        else:
            edge = "even"
        lines.append(f"| {key} | {a_value} | {b_value} | {edge} |")

    lines.append(
        f"| iq_score | {int(a.get('iq_score', 0))} | {int(b.get('iq_score', 0))} | "
        f"{iq_edge(a, b)} |"
    )
    return lines


def iq_edge(a: dict[str, Any], b: dict[str, Any]) -> str:
    a_value = int(a.get("iq_score", 0))
    b_value = int(b.get("iq_score", 0))
    if a_value > b_value:
        return str(a.get("name"))
    if b_value > a_value:
        return str(b.get("name"))
    return "even"


def top_evidence(character: dict[str, Any], mode: str, limit: int) -> list[str]:
    if mode == "iq":
        evidence = character.get("iq_evidence") or []
    elif mode == "balanced":
        evidence = list(character.get("iq_evidence") or [])
        score_evidence = character.get("score_evidence") or {}
        for key in SCORE_KEYS:
            evidence.extend(score_evidence.get(key) or [])
    else:
        evidence = []
        score_evidence = character.get("score_evidence") or {}
        for key in SCORE_KEYS:
            evidence.extend(score_evidence.get(key) or [])

    evidence = sorted(
        evidence,
        key=lambda item: (-int(item.get("points", 0)), str(item.get("sentence", ""))),
    )
    if not evidence:
        return ["- no matched Wikipedia evidence"]

    return [
        f"- {item.get('sentence', '')} [{item.get('rule', '')}, +{item.get('points', 0)}]"
        for item in evidence[:limit]
    ]


def render_battle(a: dict[str, Any], b: dict[str, Any], mode: str, max_evidence: int) -> str:
    lines = [
        f"# Battle Mode: {a.get('name')} vs {b.get('name')}",
        "",
        "This is not a full fictional combat simulation. It compares only the scores and evidence text present in Wikipedia-derived records.",
        "",
        f"- mode: {mode}",
        f"- A score: {mode_score(a, mode)}",
        f"- B score: {mode_score(b, mode)}",
        f"- verdict: {verdict(a, b, mode)}",
        "",
        "## Score Comparison",
        "",
        *dimension_table(a, b),
        "",
        f"## Evidence: {a.get('name')}",
        "",
        *top_evidence(a, mode, max_evidence),
        "",
        f"## Evidence: {b.get('name')}",
        "",
        *top_evidence(b, mode, max_evidence),
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare two characters by evidence scores.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--a", required=True, help="First character name or unique substring.")
    parser.add_argument("--b", required=True, help="Second character name or unique substring.")
    parser.add_argument("--mode", choices=["power", "iq", "balanced"], default="power")
    parser.add_argument("--max-evidence", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    a = find_character(data["characters"], args.a)
    b = find_character(data["characters"], args.b)
    output = render_battle(a, b, args.mode, args.max_evidence)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
