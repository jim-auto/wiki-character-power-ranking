"""Generate rankings with filters and evidence output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")
SCORE_KEYS = ["attack", "defense", "speed", "abilities", "feats", "scale"]
RANKING_SCORE_KEYS = ["total_score", "iq_score", *SCORE_KEYS]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def normalize_text(value: str | None) -> str | None:
    return value.lower() if value else None


def in_range(value: int, minimum: int | None, maximum: int | None) -> bool:
    if minimum is not None and value < minimum:
        return False
    if maximum is not None and value > maximum:
        return False
    return True


def filter_characters(
    characters: list[dict[str, Any]],
    *,
    media_type: str | None = None,
    universe: str | None = None,
    score_key: str = "total_score",
    min_score: int | None = None,
    max_score: int | None = None,
) -> list[dict[str, Any]]:
    wanted_media = normalize_text(media_type)
    wanted_universe = normalize_text(universe)

    filtered: list[dict[str, Any]] = []
    for character in characters:
        if wanted_media and normalize_text(str(character.get("media_type"))) != wanted_media:
            continue
        if wanted_universe and normalize_text(str(character.get("universe"))) != wanted_universe:
            continue

        if score_key == "total_score":
            score = int(character.get("total_score", 0))
        elif score_key == "iq_score":
            score = int(character.get("iq_score", 0))
        else:
            score = int((character.get("scores") or {}).get(score_key, 0))
        if not in_range(score, min_score, max_score):
            continue
        filtered.append(character)

    return filtered


def sorted_ranking(characters: list[dict[str, Any]], ranking_type: str) -> list[dict[str, Any]]:
    primary_key = "iq_score" if ranking_type == "iq" else "total_score"
    return sorted(
        characters,
        key=lambda character: (
            int(character.get(primary_key, 0)),
            int(character.get("total_score", 0)),
            str(character.get("name", "")),
        ),
        reverse=True,
    )


def render_score_line(character: dict[str, Any]) -> str:
    scores = character.get("scores") or {}
    parts = [f"{key}={int(scores.get(key, 0))}" for key in SCORE_KEYS]
    return ", ".join(parts)


def render_evidence(character: dict[str, Any], max_evidence: int) -> list[str]:
    score_evidence = character.get("score_evidence") or {}
    lines: list[str] = []

    for key in SCORE_KEYS:
        evidence_items = score_evidence.get(key) or []
        if not evidence_items:
            lines.append(f"  - {key}: no matched Wikipedia evidence")
            continue
        shown = evidence_items[:max_evidence]
        compact = " / ".join(
            f"{item.get('sentence', '')} [{item.get('rule', '')}, +{item.get('points', 0)}]"
            for item in shown
        )
        lines.append(f"  - {key}: {compact}")

    return lines


def render_iq_evidence(character: dict[str, Any], max_evidence: int) -> list[str]:
    evidence_items = character.get("iq_evidence") or []
    if not evidence_items:
        return ["  - iq: no matched Wikipedia evidence"]

    lines: list[str] = []
    for item in evidence_items[:max_evidence]:
        lines.append(
            f"  - iq: {item.get('sentence', '')} "
            f"[{item.get('rule', '')}, +{item.get('points', 0)}]"
        )
    return lines


def render_markdown(
    characters: list[dict[str, Any]],
    max_evidence: int,
    ranking_type: str,
) -> str:
    title = "Character IQ Ranking" if ranking_type == "iq" else "Character Power Ranking"
    lines = [f"# {title}", ""]

    for index, character in enumerate(characters, start=1):
        name = character.get("name", "unknown")
        tier = character.get("tier", "C")
        total = int(character.get("total_score", 0))
        iq_score = int(character.get("iq_score", 0))
        url = character.get("wikipedia_url", "")
        media_type = character.get("media_type", "")
        universe = character.get("universe", "")

        if ranking_type == "iq":
            lines.append(f"## {index}. {name} - IQ evidence score {iq_score}/10")
        else:
            lines.append(f"## {index}. {name} - {total} pts / Tier {tier}")
        lines.append(f"- source: {url}")
        lines.append(f"- media_type: {media_type}")
        lines.append(f"- universe: {universe}")
        lines.append(f"- iq_score: {iq_score}")
        lines.append(f"- scores: {render_score_line(character)}")
        lines.append("- evidence:")
        if ranking_type == "iq":
            lines.extend(render_iq_evidence(character, max_evidence))
        else:
            lines.extend(render_evidence(character, max_evidence))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def serializable_character(character: dict[str, Any], max_evidence: int) -> dict[str, Any]:
    result = dict(character)
    score_evidence = result.get("score_evidence") or {}
    result["score_evidence"] = {
        key: (score_evidence.get(key) or [])[:max_evidence] for key in SCORE_KEYS
    }
    result["iq_evidence"] = (result.get("iq_evidence") or [])[:max_evidence]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a filtered power ranking.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument(
        "--ranking-type",
        choices=["power", "iq"],
        default="power",
        help="Use total power score or the text-evidence IQ score for sorting.",
    )
    parser.add_argument("--media-type", choices=["manga", "anime", "movie", "comic"])
    parser.add_argument("--universe")
    parser.add_argument(
        "--score-key",
        choices=RANKING_SCORE_KEYS,
        default=None,
        help="Score used by --min-score and --max-score.",
    )
    parser.add_argument("--min-score", type=int)
    parser.add_argument("--max-score", type=int)
    parser.add_argument("--max-evidence", type=int, default=2)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    score_key = args.score_key or ("iq_score" if args.ranking_type == "iq" else "total_score")
    filtered = filter_characters(
        data["characters"],
        media_type=args.media_type,
        universe=args.universe,
        score_key=score_key,
        min_score=args.min_score,
        max_score=args.max_score,
    )
    ranked = sorted_ranking(filtered, args.ranking_type)

    if args.format == "json":
        output = json.dumps(
            [serializable_character(character, args.max_evidence) for character in ranked],
            ensure_ascii=False,
            indent=2,
        )
    else:
        output = render_markdown(ranked, args.max_evidence, args.ranking_type)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
