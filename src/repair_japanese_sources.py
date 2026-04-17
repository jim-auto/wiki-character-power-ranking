"""Repair Japanese display names and unsafe Japanese Wikipedia fallbacks.

This script is intentionally conservative. It trusts Japanese Wikipedia
sitelinks when Wikidata describes the source item as a fictional character.
When a character has no Japanese character page, it falls back to a relevant
Japanese Wikipedia work/franchise page instead of keeping an unrelated search
result.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import yaml

from fetch_wikipedia import parse_wikipedia_url
from resolve_ja_wikipedia import (
    DEFAULT_USER_AGENT,
    chunked,
    fetch_wikibase_ids,
    request_json,
)


DEFAULT_INPUT = Path("data/seed_characters.yaml")
DEFAULT_OUTPUT = Path("data/seed_characters.yaml")
DEFAULT_REPORT = Path("data/source_repair_report.yaml")


UNIVERSE_FALLBACK_TITLES = {
    "A Nightmare on Elm Street": "エルム街の悪夢",
    "Alien": "エイリアン (映画)",
    "Astro Boy": "鉄腕アトム",
    "Attack on Titan": "進撃の巨人の登場人物",
    "Avatar": "アバター (映画)",
    "Back to the Future": "バック・トゥ・ザ・フューチャー",
    "Battle Angel Alita": "銃夢",
    "Berserk": "ベルセルク (漫画)",
    "Blade Runner": "ブレードランナー",
    "Bleach": "BLEACHの登場人物",
    "Bourne": "ジェイソン・ボーン",
    "Cardcaptor Sakura": "カードキャプターさくら",
    "Chainsaw Man": "チェンソーマン",
    "Charlie and the Chocolate Factory": "チョコレート工場の秘密",
    "Child's Play": "チャイルド・プレイ",
    "Code Geass": "コードギアス 反逆のルルーシュの登場人物",
    "Cowboy Bebop": "カウボーイビバップ",
    "DC": "DCコミックス",
    "DCEU": "DCエクステンデッド・ユニバース",
    "Dark Knight Trilogy": "ダークナイト",
    "Death Note": "DEATH NOTEの登場人物",
    "Demon Slayer": "鬼滅の刃の登場人物一覧",
    "Die Hard": "ダイ・ハード",
    "Disney": "ディズニーキャラクター",
    "Doraemon": "ドラえもんの登場人物一覧",
    "Dragon Ball": "ドラゴンボールの登場人物",
    "Fairy Tail": "FAIRY TAILの登場人物",
    "Fight Club": "ファイト・クラブ",
    "Fist of the North Star": "北斗の拳の登場人物一覧",
    "Forrest Gump": "フォレスト・ガンプ/一期一会",
    "Friday the 13th": "13日の金曜日 (映画)",
    "Frozen": "アナと雪の女王",
    "Fullmetal Alchemist": "鋼の錬金術師",
    "Ghost in the Shell": "攻殻機動隊",
    "Gladiator": "グラディエーター",
    "Godzilla": "ゴジラ",
    "Gundam": "ガンダムシリーズ一覧",
    "Halloween": "ハロウィン (映画)",
    "Hannibal Lecter": "ハンニバル・レクター",
    "Harry Potter": "ハリー・ポッターシリーズ",
    "Hellraiser": "ヘル・レイザー",
    "Hellsing": "HELLSING",
    "Hunter x Hunter": "HUNTER×HUNTERの登場人物",
    "Indiana Jones": "インディ・ジョーンズ シリーズ",
    "Inuyasha": "犬夜叉の登場人物",
    "James Bond": "ジェームズ・ボンド",
    "JoJo's Bizarre Adventure": "ジョジョの奇妙な冒険",
    "John Wick": "ジョン・ウィック",
    "Judge Dredd": "ジャッジ・ドレッド",
    "Jujutsu Kaisen": "呪術廻戦",
    "Kill Bill": "キル・ビル",
    "King Kong": "キングコング",
    "MCU": "マーベル・シネマティック・ユニバース",
    "Mad Max": "マッドマックス",
    "Marvel": "マーベル・コミック",
    "Mary Poppins": "メリー・ポピンズ",
    "Mission: Impossible": "ミッション:インポッシブル",
    "Mob Psycho 100": "モブサイコ100",
    "My Hero Academia": "僕のヒーローアカデミア",
    "Naruto": "NARUTO -ナルト-の登場人物",
    "Neon Genesis Evangelion": "新世紀エヴァンゲリオンの登場人物",
    "One Piece": "ONE PIECEの登場人物一覧",
    "One-Punch Man": "ワンパンマン",
    "Pirates of the Caribbean": "パイレーツ・オブ・カリビアン",
    "Pokemon": "ポケットモンスターの登場人物",
    "Predator": "プレデター (映画)",
    "Psycho": "サイコ (1960年の映画)",
    "Rambo": "ランボー",
    "Ranma 1/2": "らんま1/2の登場人物",
    "RoboCop": "ロボコップ",
    "Rocky": "ロッキー (映画)",
    "Rurouni Kenshin": "るろうに剣心 -明治剣客浪漫譚-の登場人物一覧",
    "Sailor Moon": "美少女戦士セーラームーンの登場人物",
    "Scarface": "スカーフェイス",
    "Scream": "スクリーム (映画)",
    "Star Wars": "スター・ウォーズの登場人物一覧",
    "Taxi Driver": "タクシードライバー",
    "Terminator": "ターミネーター (映画)",
    "The Big Lebowski": "ビッグ・リボウスキ",
    "The Godfather": "ゴッドファーザー (映画)",
    "The Hunger Games": "ハンガー・ゲーム",
    "The Lord of the Rings": "指輪物語",
    "The Matrix": "マトリックス (映画)",
    "The Shining": "シャイニング (映画)",
    "The Texas Chainsaw Massacre": "悪魔のいけにえ",
    "Tokyo Ghoul": "東京喰種トーキョーグール",
    "Tomb Raider": "トゥームレイダー",
    "Toy Story": "トイ・ストーリー",
    "Trigun": "トライガン",
    "Urusei Yatsura": "うる星やつらの登場人物",
    "Vinland Saga": "ヴィンランド・サガ",
    "Yu-Gi-Oh!": "遊☆戯☆王の登場人物",
    "YuYu Hakusho": "幽☆遊☆白書の登場人物一覧",
}


NAME_OVERRIDES = {
    "Android 17": "人造人間17号",
    "Goku Black": "ゴクウブラック",
    "Kaido": "カイドウ",
    "Pain": "ペイン",
    "Tsunade": "綱手",
    "Minato Namikaze": "波風ミナト",
    "Portgas D. Ace": "ポートガス・D・エース",
    "Jinbe": "ジンベエ",
    "Sabo": "サボ",
    "Boa Hancock": "ボア・ハンコック",
    "Donquixote Doflamingo": "ドンキホーテ・ドフラミンゴ",
    "Buggy": "バギー",
    "Crocodile": "クロコダイル",
    "Dracule Mihawk": "ジュラキュール・ミホーク",
    "Whitebeard": "エドワード・ニューゲート",
    "Yoruichi Shihouin": "四楓院夜一",
    "Kisuke Urahara": "浦原喜助",
    "Grimmjow Jaegerjaquez": "グリムジョー・ジャガージャック",
    "Shinobu Kocho": "胡蝶しのぶ",
    "Mitsuri Kanroji": "甘露寺蜜璃",
    "Muichiro Tokito": "時透無一郎",
    "Tengen Uzui": "宇髄天元",
    "Gyomei Himejima": "悲鳴嶼行冥",
    "Sanemi Shinazugawa": "不死川実弥",
    "Muzan Kibutsuji": "鬼舞辻無惨",
    "Akaza": "猗窩座",
    "Erwin Smith": "エルヴィン・スミス",
    "Annie Leonhart": "アニ・レオンハート",
    "Zeke Yeager": "ジーク・イェーガー",
    "Historia Reiss": "ヒストリア・レイス",
    "Yuta Okkotsu": "乙骨憂太",
    "Askeladd": "アシェラッド",
    "Thorfinn": "トルフィン",
    "Endeavor": "エンデヴァー",
    "Hawks": "ホークス",
    "Dabi": "荼毘",
    "Himiko Toga": "トガヒミコ",
    "Eijiro Kirishima": "切島鋭児郎",
    "Tsuyu Asui": "蛙吹梅雨",
    "Shota Aizawa": "相澤消太",
    "Josuke Higashikata": "東方仗助",
    "Yoshikage Kira": "吉良吉影",
    "Bruno Bucciarati": "ブローノ・ブチャラティ",
    "Jolyne Cujoh": "空条徐倫",
    "Enrico Pucci": "エンリコ・プッチ",
    "Leorio Paradinight": "レオリオ",
    "Chrollo Lucilfer": "クロロ＝ルシルフル",
    "Isaac Netero": "アイザック＝ネテロ",
    "Joey Wheeler": "城之内克也",
    "Mewtwo": "ミュウツー",
    "Meowth": "ニャース",
    "Riza Hawkeye": "リザ・ホークアイ",
    "Near": "ニア",
    "Scar": "スカー",
    "Alucard": "アーカード",
    "Vash the Stampede": "ヴァッシュ・ザ・スタンピード",
    "Alita": "ガリィ",
    "Kagome Higurashi": "日暮かごめ",
    "Sesshomaru": "殺生丸",
    "Akane Tendo": "天道あかね",
    "Sam Wilson (MCU)": "サム・ウィルソン（MCU）",
    "Scott Lang (MCU)": "スコット・ラング（MCU）",
    "Hope van Dyne (MCU)": "ホープ・ヴァン・ダイン（MCU）",
    "Gamora (MCU)": "ガモーラ（MCU）",
    "Drax (MCU)": "ドラックス（MCU）",
    "Groot (MCU)": "グルート（MCU）",
    "Nick Fury (MCU)": "ニック・フューリー（MCU）",
    "Nebula (MCU)": "ネビュラ（MCU）",
    "Mantis (MCU)": "マンティス（MCU）",
    "Wong (MCU)": "ウォン（MCU）",
    "Shuri (MCU)": "シュリ（MCU）",
    "Alastor Moody": "アラスター・ムーディ",
    "Anakin Skywalker": "アナキン・スカイウォーカー",
    "Jessie": "ムサシ",
    "James": "コジロウ",
    "Joker (The Dark Knight)": "ジョーカー（ダークナイト）",
    "Harley Quinn (DCEU)": "ハーレイ・クイン（DCEU）",
    "Clark Kent (DCEU)": "クラーク・ケント（DCEU）",
    "Bruce Wayne (DCEU)": "ブルース・ウェイン（DCEU）",
    "Diana Prince (DCEU)": "ダイアナ・プリンス（DCEU）",
    "Arthur Curry (DCEU)": "アーサー・カリー（DCEU）",
    "Barry Allen (DCEU)": "バリー・アレン（DCEU）",
    "Samwise Gamgee": "サムワイズ・ギャムジー",
    "Mulan": "ムーラン",
    "Forrest Gump": "フォレスト・ガンプ",
    "The Dude": "デュード",
    "Maximus": "マキシマス",
    "Max Rockatansky": "マックス・ロカタンスキー",
    "Marty McFly": "マーティ・マクフライ",
    "Doc Brown": "エメット・ブラウン",
    "Jake Sully": "ジェイク・サリー",
    "Neytiri": "ネイティリ",
    "Simba": "シンバ",
    "Pinhead": "ピンヘッド",
    "Invisible Woman": "インビジブル・ウーマン",
    "Thing": "シング",
    "Rogue": "ローグ",
    "Colossus": "コロッサス",
    "Emma Frost": "エマ・フロスト",
    "Psylocke": "サイロック",
    "Bishop": "ビショップ",
    "Apocalypse": "アポカリプス",
    "Juggernaut": "ジャガーノート",
    "Sabretooth": "セイバートゥース",
    "Hercules": "ヘラクレス",
    "Nova": "ノヴァ",
    "Moon Girl": "ムーンガール",
    "Squirrel Girl": "スクイレル・ガール",
    "Wally West": "ウォーリー・ウェスト",
    "Alan Scott": "アラン・スコット",
    "Donna Troy": "ドナ・トロイ",
    "Doctor Fate": "ドクター・フェイト",
    "Blue Beetle": "ブルービートル",
    "Booster Gold": "ブースターゴールド",
    "Lobo": "ロボ",
    "Etrigan": "エトリガン",
    "The Spectre": "スペクター",
    "Mister Miracle": "ミスター・ミラクル",
    "Big Barda": "ビッグ・バルダ",
    "Vandal Savage": "ヴァンダル・サベッジ",
    "Rorschach": "ロールシャッハ",
    "Bullseye": "ブルズアイ",
}


URL_FALLBACK_NAME_OVERRIDES = {
    "Kaido",
    "Jinbe",
    "Endeavor",
    "Shota Aizawa",
    "Bullseye",
}


CHARACTER_DESCRIPTION_PATTERNS = [
    r"架空",
    r"登場",
    r"キャラクター",
    r"人物",
    r"スーパーヒーロー",
    r"ヴィラン",
    r"fictional",
    r"character",
    r"superhero",
    r"supervillain",
    r"villain",
    r"protagonist",
    r"antagonist",
]

NON_CHARACTER_DESCRIPTION_PATTERNS = [
    r"一覧",
    r"ウィキメディア",
    r"曖昧さ回避",
    r"シングル",
    r"アルバム",
    r"道路",
    r"俳優",
    r"声優",
    r"科学者",
    r"選手",
    r"年表",
    r"コンピュータゲーム",
]

SUSPICIOUS_TITLE_PATTERNS = [
    r"曖昧さ回避",
    r"バージョン履歴",
    r"年表",
    r"コンピュータゲーム",
    r"サウンドトラック",
    r"ラッパー",
    r"科学者",
    r"選手",
    r"王\)",
    r"テスト",
]


ASCII_NAME_PATTERN = re.compile(r"^[\x00-\x7f（）() .,'’:\-!/]+$")


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False, width=1000)
    temp_path.replace(path)


def build_ja_url(title: str) -> str:
    return f"https://ja.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"


def clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", label).strip()


def is_ascii_name(value: str) -> bool:
    return bool(ASCII_NAME_PATTERN.fullmatch(value))


def looks_like_character(ja_description: str | None, en_description: str | None) -> bool:
    text = f"{ja_description or ''} {en_description or ''}".casefold()
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in NON_CHARACTER_DESCRIPTION_PATTERNS):
        if not any(token in text for token in ["架空", "fictional", "character", "スーパーヒーロー"]):
            return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in CHARACTER_DESCRIPTION_PATTERNS)


def suspicious_title(url: str) -> bool:
    try:
        _host, title = parse_wikipedia_url(url)
    except ValueError:
        return True
    return any(re.search(pattern, title, re.IGNORECASE) for pattern in SUSPICIOUS_TITLE_PATTERNS)


def fetch_entities(seed: dict[str, Any], timeout: int, user_agent: str) -> dict[str, dict[str, Any]]:
    pairs: list[tuple[str, str, str]] = []
    for character in seed["characters"]:
        url = str(character.get("source_wikipedia_url_original") or character["wikipedia_url"])
        host, title = parse_wikipedia_url(url)
        pairs.append((url, host, title))

    qids_by_url = fetch_wikibase_ids(pairs, timeout=timeout, user_agent=user_agent)
    entities: dict[str, dict[str, Any]] = {}
    for batch in chunked(sorted(set(qids_by_url.values())), 50):
        payload = request_json(
            "https://www.wikidata.org/w/api.php?"
            + urlencode(
                {
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(batch),
                    "props": "labels|descriptions|sitelinks/urls",
                    "languages": "ja|en",
                    "sitefilter": "jawiki",
                },
                quote_via=quote,
            ),
            timeout=timeout,
            user_agent=user_agent,
        )
        entities.update(payload.get("entities", {}))
        time.sleep(0.1)

    by_url: dict[str, dict[str, Any]] = {}
    for url, qid in qids_by_url.items():
        by_url[url] = {"qid": qid, "entity": entities.get(qid, {})}
    return by_url


def repair(seed: dict[str, Any], *, timeout: int, user_agent: str) -> tuple[dict[str, Any], dict[str, Any]]:
    entities_by_url = fetch_entities(seed, timeout, user_agent)
    name_changes: list[dict[str, Any]] = []
    url_changes: list[dict[str, Any]] = []
    untouched = 0

    for character in seed["characters"]:
        current_name = str(character["name"])
        old_name = str(character.get("source_name_original") or current_name)
        old_url = str(character["wikipedia_url"])
        original_url = str(character.get("source_wikipedia_url_original") or old_url)
        entity_info = entities_by_url.get(original_url, {})
        entity = entity_info.get("entity") or {}
        qid = entity_info.get("qid")
        labels = entity.get("labels") or {}
        descriptions = entity.get("descriptions") or {}
        ja_label = clean_label(((labels.get("ja") or {}).get("value")) or "")
        ja_description = (descriptions.get("ja") or {}).get("value")
        en_description = (descriptions.get("en") or {}).get("value")
        jawiki_url = (((entity.get("sitelinks") or {}).get("jawiki") or {}).get("url"))
        is_character = looks_like_character(ja_description, en_description)

        new_name = NAME_OVERRIDES.get(old_name)
        if not new_name and is_ascii_name(old_name) and is_character and ja_label:
            new_name = ja_label
        if not new_name:
            new_name = old_name
        if new_name != current_name:
            character["name"] = new_name
            if new_name != old_name:
                character["source_name_original"] = old_name
            else:
                character.pop("source_name_original", None)
            name_changes.append({"old_name": old_name, "new_name": new_name})

        new_url = old_url
        resolution = character.get("source_resolution")
        if is_character and jawiki_url:
            new_url = str(jawiki_url)
            resolution = "wikidata_jawiki_character"
        elif (
            old_name in URL_FALLBACK_NAME_OVERRIDES
            or character.get("source_resolution") == "universe_fallback"
            or character.get("source_resolution") == "jawiki_search_fallback"
            or suspicious_title(old_url)
        ):
            fallback_title = UNIVERSE_FALLBACK_TITLES.get(str(character.get("universe")))
            if fallback_title:
                new_url = build_ja_url(fallback_title)
                resolution = "universe_fallback"

        if new_url != old_url:
            character["wikipedia_url"] = new_url
            character["source_wikipedia_url_original"] = original_url
            character["source_resolution"] = resolution
            url_changes.append(
                {
                    "name": character["name"],
                    "old_url": old_url,
                    "new_url": new_url,
                    "resolution": resolution,
                    "wikidata_id": qid,
                    "wikidata_ja_label": ja_label,
                }
            )
        else:
            untouched += 1

        if qid:
            character["source_wikidata_id"] = qid
        if ja_label:
            character["source_wikidata_label_ja"] = ja_label

    remaining_ascii_names = [
        str(character["name"])
        for character in seed["characters"]
        if is_ascii_name(str(character["name"]))
    ]
    report = {
        "total": len(seed["characters"]),
        "name_changes_this_run": len(name_changes),
        "url_changes_this_run": len(url_changes),
        "normalized_names_total": sum(
            1 for character in seed["characters"] if character.get("source_name_original")
        ),
        "universe_fallback_urls_total": sum(
            1
            for character in seed["characters"]
            if character.get("source_resolution") == "universe_fallback"
        ),
        "wikidata_character_urls_total": sum(
            1
            for character in seed["characters"]
            if character.get("source_resolution") == "wikidata_jawiki_character"
        ),
        "remaining_ascii_names": remaining_ascii_names,
        "untouched_urls": untouched,
        "name_change_items": name_changes,
        "url_change_items": url_changes,
    }
    return seed, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair Japanese names and unsafe source URLs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    seed = load_yaml(args.input)
    updated, report = repair(seed, timeout=args.timeout, user_agent=args.user_agent)
    if not args.dry_run:
        save_yaml(args.output, updated)
        save_yaml(args.report, report)
    summary_keys = (
        "total",
        "name_changes_this_run",
        "url_changes_this_run",
        "normalized_names_total",
        "universe_fallback_urls_total",
        "remaining_ascii_names",
    )
    print(json.dumps({key: report[key] for key in summary_keys}, ensure_ascii=False))


if __name__ == "__main__":
    main()
