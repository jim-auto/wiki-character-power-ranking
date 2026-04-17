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
CONDITION_LABELS = {
    "superpower": "超能力あり",
    "modified": "改造あり",
    "technology": "技術/装備",
    "magic": "魔法/呪い",
    "weapon": "武器あり",
    "non_human": "人間以外",
    "god_or_deity": "神格",
    "alien": "宇宙人",
    "robot_ai": "ロボット/AI",
    "martial_artist": "格闘",
    "military": "軍人/兵士",
    "leader": "リーダー",
    "detective_genius": "天才/探偵",
    "transformation": "変身",
    "immortal": "不死/再生",
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def find_character(characters: list[dict[str, Any]], query: str) -> dict[str, Any]:
    normalized = query.strip().casefold()

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


def stage_candidates(version: dict[str, Any]) -> list[str]:
    values = [str(version.get("label") or "")]
    aliases = version.get("aliases") or []
    if isinstance(aliases, list):
        values.extend(str(alias) for alias in aliases)
    return [value.strip() for value in values if value and value.strip()]


def find_version(character: dict[str, Any], stage: str) -> dict[str, Any]:
    normalized = stage.strip().casefold()
    if not normalized:
        return dict(character)

    versions = [version for version in character.get("versions") or [] if isinstance(version, dict)]
    exact_matches = [
        version
        for version in versions
        if any(candidate.casefold() == normalized for candidate in stage_candidates(version))
    ]
    prefix_matches = [
        version
        for version in versions
        if any(candidate.casefold().startswith(normalized) for candidate in stage_candidates(version))
    ]
    contains_matches = [
        version
        for version in versions
        if any(normalized in candidate.casefold() for candidate in stage_candidates(version))
    ]

    for matches in (exact_matches, prefix_matches, contains_matches):
        if matches:
            selected = dict(matches[0])
            selected["name"] = character.get("name")
            selected["_stage_label"] = selected.get("label") or stage
            return selected

    available = ", ".join(str(version.get("label")) for version in versions if version.get("label"))
    suffix = f" 利用可能な時点: {available}" if available else " 利用可能な時点はありません。"
    raise ValueError(f"{character.get('name')} に時点 '{stage}' は見つかりません。{suffix}")


def mode_score(character: dict[str, Any], mode: str) -> int:
    if mode == "iq":
        return int(character.get("iq_score", 0))
    if mode == "balanced":
        return int(character.get("total_score", 0)) + int(character.get("iq_score", 0))
    return int(character.get("total_score", 0))


def normalize_conditions(values: list[str] | None) -> list[str]:
    conditions: list[str] = []
    for raw_value in values or []:
        for value in raw_value.split(","):
            key = value.strip()
            if not key:
                continue
            if key not in CONDITION_LABELS:
                valid = ", ".join(CONDITION_LABELS)
                raise ValueError(f"Unknown condition: {key}. Valid conditions: {valid}")
            if key not in conditions:
                conditions.append(key)
    return conditions


def explicit_iq_text(character: dict[str, Any]) -> str:
    value = character.get("explicit_iq")
    return str(value) if isinstance(value, int) else "記述なし"


def estimated_iq_text(character: dict[str, Any]) -> str:
    estimated = character.get("estimated_iq") or {}
    label = str(estimated.get("label") or "推定不可")
    estimated_range = estimated.get("range")
    suffix = f"（{estimated_range}）" if estimated_range else ""
    return f"{label}{suffix}"


def battle_display_name(character: dict[str, Any], stage: str = "") -> str:
    clean_stage = stage.strip() or str(character.get("_stage_label") or "").strip()
    name = str(character.get("name"))
    return f"{name}（{clean_stage}）" if clean_stage else name


def explicit_iq_edge(a: dict[str, Any], b: dict[str, Any], a_stage: str = "", b_stage: str = "") -> str:
    a_value = a.get("explicit_iq")
    b_value = b.get("explicit_iq")
    if not isinstance(a_value, int) or not isinstance(b_value, int):
        return "比較不可"
    if a_value > b_value:
        return battle_display_name(a, a_stage)
    if b_value > a_value:
        return battle_display_name(b, b_stage)
    return "互角"


def verdict(a: dict[str, Any], b: dict[str, Any], mode: str, a_stage: str = "", b_stage: str = "") -> str:
    a_score = mode_score(a, mode)
    b_score = mode_score(b, mode)
    diff = a_score - b_score

    if diff == 0:
        return "現在のWikipedia根拠スコアでは引き分けです。"

    winner = a if diff > 0 else b
    winner_stage = a_stage if diff > 0 else b_stage
    margin = abs(diff)
    strength = "優勢" if margin >= 8 else "やや優勢"
    return f"{battle_display_name(winner, winner_stage)} が {MODE_LABELS.get(mode, mode)} モードで {margin} 点差の{strength}です。"


def dimension_table(a: dict[str, Any], b: dict[str, Any], a_stage: str = "", b_stage: str = "") -> list[str]:
    a_scores = a.get("scores") or {}
    b_scores = b.get("scores") or {}
    a_name = battle_display_name(a, a_stage)
    b_name = battle_display_name(b, b_stage)
    lines = ["| 項目 | A | B | 優勢 |", "| --- | ---: | ---: | --- |"]

    for key in SCORE_KEYS:
        a_value = int(a_scores.get(key, 0))
        b_value = int(b_scores.get(key, 0))
        if a_value > b_value:
            edge = a_name
        elif b_value > a_value:
            edge = b_name
        else:
            edge = "互角"
        lines.append(f"| {SCORE_LABELS[key]} | {a_value} | {b_value} | {edge} |")

    lines.append(
        f"| 知性スコア | {int(a.get('iq_score', 0))} | {int(b.get('iq_score', 0))} | "
        f"{iq_edge(a, b, a_stage, b_stage)} |"
    )
    lines.append(
        f"| 明示IQ | {explicit_iq_text(a)} | {explicit_iq_text(b)} | {explicit_iq_edge(a, b, a_stage, b_stage)} |"
    )
    lines.append(
        f"| 推定IQ | {estimated_iq_text(a)} | {estimated_iq_text(b)} | {iq_edge(a, b, a_stage, b_stage)} |"
    )
    return lines


def iq_edge(a: dict[str, Any], b: dict[str, Any], a_stage: str = "", b_stage: str = "") -> str:
    a_value = int(a.get("iq_score", 0))
    b_value = int(b.get("iq_score", 0))
    if a_value > b_value:
        return battle_display_name(a, a_stage)
    if b_value > a_value:
        return battle_display_name(b, b_stage)
    return "互角"


def condition_match_count(character: dict[str, Any], conditions: list[str]) -> int:
    flags = character.get("condition_flags") or {}
    return sum(1 for condition in conditions if bool(flags.get(condition)))


def condition_table(a: dict[str, Any], b: dict[str, Any], conditions: list[str]) -> list[str]:
    if not conditions:
        return []

    a_flags = a.get("condition_flags") or {}
    b_flags = b.get("condition_flags") or {}
    lines = [
        "## 条件照合",
        "",
        f"- A条件一致: {condition_match_count(a, conditions)}/{len(conditions)}",
        f"- B条件一致: {condition_match_count(b, conditions)}/{len(conditions)}",
        "",
        "| 条件 | A | B |",
        "| --- | --- | --- |",
    ]
    for condition in conditions:
        label = CONDITION_LABELS[condition]
        a_value = "該当" if a_flags.get(condition) else "非該当"
        b_value = "該当" if b_flags.get(condition) else "非該当"
        lines.append(f"| {label} | {a_value} | {b_value} |")
    lines.append("")
    return lines


def top_evidence(character: dict[str, Any], mode: str, limit: int) -> list[str]:
    if mode == "iq":
        evidence = list(character.get("iq_evidence") or [])
        explicit_evidence = character.get("explicit_iq_evidence") or []
    elif mode == "balanced":
        evidence = list(character.get("iq_evidence") or [])
        explicit_evidence = character.get("explicit_iq_evidence") or []
        score_evidence = character.get("score_evidence") or {}
        for key in SCORE_KEYS:
            evidence.extend(score_evidence.get(key) or [])
    else:
        evidence = []
        explicit_evidence = []
        score_evidence = character.get("score_evidence") or {}
        for key in SCORE_KEYS:
            evidence.extend(score_evidence.get(key) or [])

    evidence = sorted(
        evidence,
        key=lambda item: (-int(item.get("points", 0)), str(item.get("sentence", ""))),
    )
    explicit_lines = [
        f"- 明示IQ {item.get('value')}: {item.get('sentence', '')} [{item.get('rule', '')}]"
        for item in explicit_evidence[:limit]
    ]
    if not evidence and not explicit_lines:
        return ["- 一致するWikipedia根拠なし"]

    score_lines = [
        f"- {item.get('sentence', '')} [{item.get('rule', '')}, +{item.get('points', 0)}]"
        for item in evidence[:limit]
    ]
    return explicit_lines + score_lines


def render_battle(
    a: dict[str, Any],
    b: dict[str, Any],
    mode: str,
    max_evidence: int,
    a_stage: str = "",
    b_stage: str = "",
    conditions: list[str] | None = None,
) -> str:
    a_name = battle_display_name(a, a_stage)
    b_name = battle_display_name(b, b_stage)
    conditions = conditions or []
    lines = [
        f"# バトル比較: {a_name} vs {b_name}",
        "",
        "これは完全な架空戦闘シミュレーションではありません。日本語版Wikipedia由来の根拠文とスコアだけで比較します。",
        "",
        f"- モード: {MODE_LABELS.get(mode, mode)}",
        f"- Aスコア: {mode_score(a, mode)}",
        f"- Bスコア: {mode_score(b, mode)}",
        *(
            [
                f"- 条件一致: A {condition_match_count(a, conditions)}/{len(conditions)} / B {condition_match_count(b, conditions)}/{len(conditions)}",
            ]
            if conditions
            else []
        ),
        f"- 判定: {verdict(a, b, mode, a_stage, b_stage)}",
        "",
        "## スコア比較",
        "",
        *dimension_table(a, b, a_stage, b_stage),
        "",
        *condition_table(a, b, conditions),
        f"## 根拠: {a_name}",
        "",
        *top_evidence(a, mode, max_evidence),
        "",
        f"## 根拠: {b_name}",
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
    parser.add_argument("--a-stage", default="", help="1人目の時点ラベル。例: 中忍試験時点")
    parser.add_argument("--b-stage", default="", help="2人目の時点ラベル。例: 中忍試験時点")
    parser.add_argument("--mode", choices=["power", "iq", "balanced"], default="power")
    parser.add_argument(
        "--condition",
        action="append",
        default=[],
        help="照合する条件キー。複数回指定、またはカンマ区切り指定が可能。例: --condition superpower,weapon",
    )
    parser.add_argument("--max-evidence", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    a = find_character(data["characters"], args.a)
    b = find_character(data["characters"], args.b)
    a = find_version(a, args.a_stage)
    b = find_version(b, args.b_stage)
    conditions = normalize_conditions(args.condition)
    output = render_battle(a, b, args.mode, args.max_evidence, conditions=conditions)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
