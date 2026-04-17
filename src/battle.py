"""Compare two characters using Wikipedia-grounded scores only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")
SCORE_KEYS = ["attack", "defense", "speed", "abilities", "feats", "scale"]
SCORE_LABELS = {
    "attack": "攻撃",
    "defense": "防御",
    "speed": "速度",
    "abilities": "能力",
    "feats": "実績",
    "scale": "影響範囲",
}
MODE_LABELS = {
    "power": "強さ",
    "iq": "知性スコア",
    "balanced": "総合",
}


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
        raise ValueError(f"キャラクター指定が曖昧です: '{query}'。一致: {names}")
    raise ValueError(f"キャラクターが見つかりません: {query}")


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
        return "現在のWikipedia根拠スコアでは引き分けです。"

    winner = a if diff > 0 else b
    margin = abs(diff)
    strength = "優勢" if margin >= 8 else "やや優勢"
    return f"{winner.get('name')} が {MODE_LABELS.get(mode, mode)} モードで {margin} 点差の{strength}です。"


def dimension_table(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    a_scores = a.get("scores") or {}
    b_scores = b.get("scores") or {}
    lines = ["| 項目 | A | B | 優勢 |", "| --- | ---: | ---: | --- |"]

    for key in SCORE_KEYS:
        a_value = int(a_scores.get(key, 0))
        b_value = int(b_scores.get(key, 0))
        if a_value > b_value:
            edge = str(a.get("name"))
        elif b_value > a_value:
            edge = str(b.get("name"))
        else:
            edge = "互角"
        lines.append(f"| {SCORE_LABELS[key]} | {a_value} | {b_value} | {edge} |")

    lines.append(
        f"| 知性スコア | {int(a.get('iq_score', 0))} | {int(b.get('iq_score', 0))} | "
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
    return "互角"


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
        return ["- 一致するWikipedia根拠なし"]

    return [
        f"- {item.get('sentence', '')} [{item.get('rule', '')}, +{item.get('points', 0)}]"
        for item in evidence[:limit]
    ]


def render_battle(a: dict[str, Any], b: dict[str, Any], mode: str, max_evidence: int) -> str:
    lines = [
        f"# バトル比較: {a.get('name')} vs {b.get('name')}",
        "",
        "これは完全な架空戦闘シミュレーションではありません。日本語版Wikipedia由来の根拠文とスコアだけで比較します。",
        "",
        f"- モード: {MODE_LABELS.get(mode, mode)}",
        f"- Aスコア: {mode_score(a, mode)}",
        f"- Bスコア: {mode_score(b, mode)}",
        f"- 判定: {verdict(a, b, mode)}",
        "",
        "## スコア比較",
        "",
        *dimension_table(a, b),
        "",
        f"## 根拠: {a.get('name')}",
        "",
        *top_evidence(a, mode, max_evidence),
        "",
        f"## 根拠: {b.get('name')}",
        "",
        *top_evidence(b, mode, max_evidence),
        "",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="2キャラクターを根拠スコアで比較します。")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--a", required=True, help="1人目のキャラクター名、または一意に絞れる部分文字列。")
    parser.add_argument("--b", required=True, help="2人目のキャラクター名、または一意に絞れる部分文字列。")
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
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
