"""Fetch optional display thumbnails from Openverse.

Openverse images are presentation metadata only. They are not used for scoring,
feature extraction, ranking, or battle comparison.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import Request, urlopen

import yaml

from fetch_wikipedia import DEFAULT_USER_AGENT


DEFAULT_INPUT = Path("data/characters.yaml")
DEFAULT_REPORT = Path("data/openverse_image_report.yaml")
OPENVERSE_IMAGE_SEARCH_URL = "https://api.openverse.org/v1/images/"
ALLOWED_LICENSES = {"cc0", "pdm", "by", "by-sa"}
BLOCKED_PROVIDERS = {"wikimedia", "wikimedia_commons"}
BLOCKED_HOST_PARTS = ("wikimedia.org", "wikipedia.org")
DEFAULT_PAGE_SIZE = 10
DEFAULT_MIN_SCORE = 70
IMAGE_FIELDS = (
    "image_url",
    "image_source",
    "image_alt",
    "image_landing_url",
    "image_creator",
    "image_creator_url",
    "image_license",
    "image_license_url",
    "image_credit",
)


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


def request_json(url: str, *, timeout: int, user_agent: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def openverse_search_url(query: str, page_size: int) -> str:
    return f"{OPENVERSE_IMAGE_SEARCH_URL}?{urlencode({
        'q': query,
        'page_size': page_size,
        'license': ','.join(sorted(ALLOWED_LICENSES)),
    })}"


def text_tokens(text: str) -> list[str]:
    tokens = [
        token
        for token in re.split(r"[^0-9a-zA-Z]+", text.casefold())
        if len(token) >= 3
    ]
    blocked = {
        "and",
        "anime",
        "character",
        "characters",
        "comic",
        "comics",
        "cosplay",
        "cosplayer",
        "film",
        "from",
        "manga",
        "movie",
        "the",
    }
    return [token for token in dict.fromkeys(tokens) if token not in blocked]


def title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    title = unquote(path.rsplit("/", 1)[-1]).replace("_", " ")
    return title.strip()


def strip_parenthetical(text: str) -> str:
    stripped = re.sub(r"\s*\([^)]*\)\s*", " ", text).strip()
    return re.sub(r"\s+", " ", stripped)


def english_name_candidates(character: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("source_name_original",):
        value = character.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    original_title = title_from_url(str(character.get("source_wikipedia_url_original") or ""))
    if original_title:
        candidates.append(original_title)
        stripped = strip_parenthetical(original_title)
        if stripped != original_title:
            candidates.append(stripped)
    return list(dict.fromkeys(candidates))


def query_candidates(character: dict[str, Any]) -> list[str]:
    names = english_name_candidates(character)
    if not names:
        return []
    universe = str(character.get("universe") or "").strip()
    queries: list[str] = []
    for name in names:
        if universe:
            queries.append(f'"{name}" "{universe}" cosplay')
        queries.append(f'"{name}" cosplay')
    return list(dict.fromkeys(queries))


def primary_name_tokens(character: dict[str, Any]) -> list[str]:
    value = character.get("source_name_original")
    if isinstance(value, str) and value.strip():
        return text_tokens(value)
    original_title = strip_parenthetical(title_from_url(str(character.get("source_wikipedia_url_original") or "")))
    return text_tokens(original_title)


def blocked_url(url: str) -> bool:
    host = urlparse(url).netloc.casefold()
    return any(part in host for part in BLOCKED_HOST_PARTS)


def normalized_source(item: dict[str, Any]) -> str:
    return str(item.get("source") or item.get("provider") or "").casefold()


def is_allowed_item(item: dict[str, Any]) -> bool:
    license_name = str(item.get("license") or "").casefold()
    if license_name not in ALLOWED_LICENSES:
        return False
    if str(item.get("source") or "").casefold() in BLOCKED_PROVIDERS:
        return False
    if str(item.get("provider") or "").casefold() in BLOCKED_PROVIDERS:
        return False
    for key in ("url", "thumbnail", "foreign_landing_url"):
        value = str(item.get(key) or "")
        if value and blocked_url(value):
            return False
    return bool(item.get("thumbnail") or item.get("url"))


def item_text(item: dict[str, Any]) -> str:
    tags = " ".join(str(tag.get("name") or "") for tag in item.get("tags") or [] if isinstance(tag, dict))
    return " ".join(
        str(item.get(key) or "")
        for key in ("title", "creator", "source", "provider")
    ) + " " + tags


def score_item(item: dict[str, Any], *, name_tokens: list[str], universe_tokens: list[str]) -> int:
    text = item_text(item).casefold()
    title = str(item.get("title") or "").casefold()
    score = 0

    matched_name_tokens = [token for token in name_tokens if token in text]
    matched_universe_tokens = [token for token in universe_tokens if token in text]
    score += len(matched_name_tokens) * 18
    score += len(matched_universe_tokens) * 8

    matched_title_tokens = [token for token in name_tokens if token in title]
    if matched_title_tokens:
        score += 12
    else:
        score -= 28
    if any(term in text for term in ("cosplay", "cosplayer", "costume")):
        score += 16
    if str(item.get("license") or "").casefold() in {"cc0", "pdm"}:
        score += 4
    if normalized_source(item) == "flickr":
        score += 3
    if any(term in text for term in ("wallpaper", "poster", "logo", "trailer")):
        score -= 18

    if not matched_name_tokens:
        score -= 60
    return score


def best_openverse_image(
    character: dict[str, Any],
    *,
    timeout: int,
    user_agent: str,
    page_size: int,
    max_queries: int,
    sleep_seconds: float,
    min_score: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    names = english_name_candidates(character)
    name_tokens = primary_name_tokens(character)
    universe_tokens = text_tokens(str(character.get("universe") or ""))

    best_item: dict[str, Any] | None = None
    best_score = -100
    attempts: list[dict[str, Any]] = []
    for query in query_candidates(character)[:max_queries]:
        try:
            payload = request_json(
                openverse_search_url(query, page_size),
                timeout=timeout,
                user_agent=user_agent,
            )
        except Exception as exc:
            attempts.append({"query": query, "error": f"{type(exc).__name__}: {exc}"})
            continue
        results = payload.get("results") or []
        for item in results:
            if not isinstance(item, dict) or not is_allowed_item(item):
                continue
            score = score_item(item, name_tokens=name_tokens, universe_tokens=universe_tokens)
            attempts.append(
                {
                    "query": query,
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "license": item.get("license"),
                    "score": score,
                }
            )
            if score > best_score:
                best_item = item
                best_score = score
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if not best_item or best_score < min_score:
        return None, attempts
    best_item["_match_score"] = best_score
    return best_item, attempts


def attribution_for(item: dict[str, Any]) -> str:
    attribution = str(item.get("attribution") or "").strip()
    if attribution:
        return attribution
    title = str(item.get("title") or "Untitled").strip()
    creator = str(item.get("creator") or "unknown creator").strip()
    license_name = str(item.get("license") or "").upper()
    return f"{title} / {creator} / {license_name}"


def apply_image(character: dict[str, Any], item: dict[str, Any]) -> None:
    character["image_url"] = str(item.get("thumbnail") or item.get("url"))
    character["image_source"] = f"openverse:{item.get('source') or item.get('provider') or 'unknown'}"
    character["image_alt"] = str(character.get("name") or "")
    character["image_landing_url"] = str(item.get("foreign_landing_url") or "")
    character["image_creator"] = str(item.get("creator") or "")
    character["image_creator_url"] = str(item.get("creator_url") or "")
    character["image_license"] = str(item.get("license") or "")
    character["image_license_url"] = str(item.get("license_url") or "")
    character["image_credit"] = attribution_for(item)


def clear_openverse_images(characters: list[dict[str, Any]]) -> int:
    cleared = 0
    for character in characters:
        if not str(character.get("image_source") or "").startswith("openverse:"):
            continue
        for field in IMAGE_FIELDS:
            character.pop(field, None)
        cleared += 1
    return cleared


def update_characters(
    data: dict[str, Any],
    *,
    timeout: int,
    user_agent: str,
    page_size: int,
    max_queries: int,
    sleep_seconds: float,
    limit: int | None,
    min_score: int,
    dry_run: bool,
    clear_existing_openverse: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    characters = data["characters"]
    cleared_openverse_images = 0
    if clear_existing_openverse and not dry_run:
        cleared_openverse_images = clear_openverse_images(characters)
    missing_before = sum(1 for character in characters if not character.get("image_url"))
    candidates = [character for character in characters if not character.get("image_url")]
    if limit is not None:
        candidates = candidates[:limit]

    found_items: list[dict[str, Any]] = []
    missing_items: list[dict[str, Any]] = []
    for character in candidates:
        item, attempts = best_openverse_image(
            character,
            timeout=timeout,
            user_agent=user_agent,
            page_size=page_size,
            max_queries=max_queries,
            sleep_seconds=sleep_seconds,
            min_score=min_score,
        )
        if not item:
            missing_items.append(
                {
                    "name": character.get("name"),
                    "queries": query_candidates(character),
                    "attempts": attempts[:5],
                }
            )
            continue
        if not dry_run:
            apply_image(character, item)
        found_items.append(
            {
                "name": character.get("name"),
                "image_url": item.get("thumbnail") or item.get("url"),
                "title": item.get("title"),
                "source": item.get("source"),
                "provider": item.get("provider"),
                "landing_url": item.get("foreign_landing_url"),
                "license": item.get("license"),
                "license_url": item.get("license_url"),
                "creator": item.get("creator"),
                "score": item.get("_match_score"),
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Openverse",
        "dry_run": dry_run,
        "total_characters": len(characters),
        "characters_without_images_before": missing_before,
        "candidates_checked": len(candidates),
        "images_found": len(found_items),
        "characters_without_images_after": sum(1 for character in characters if not character.get("image_url")),
        "cleared_openverse_images": cleared_openverse_images,
        "allowed_licenses": sorted(ALLOWED_LICENSES),
        "blocked_providers": sorted(BLOCKED_PROVIDERS),
        "max_queries_per_character": max_queries,
        "min_score": min_score,
        "items": found_items,
        "missing_items": missing_items,
    }
    return data, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch non-Wikimedia Openverse thumbnails for display.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-queries", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clear-existing-openverse", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    updated_data, report = update_characters(
        data,
        timeout=args.timeout,
        user_agent=args.user_agent,
        page_size=args.page_size,
        max_queries=args.max_queries,
        sleep_seconds=args.sleep,
        limit=args.limit,
        min_score=args.min_score,
        dry_run=args.dry_run,
        clear_existing_openverse=args.clear_existing_openverse,
    )
    if not args.dry_run:
        save_yaml(args.output, updated_data)
    save_yaml(args.report, report)


if __name__ == "__main__":
    main()
