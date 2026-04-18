"""Fetch optional display thumbnails from configured Fandom wikis.

Fandom images are presentation metadata only. They are not used for scoring,
feature extraction, ranking, or battle comparison. Existing Wikimedia images are
kept by default; this script fills characters that still have no image.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

import yaml

from fetch_wikipedia import DEFAULT_USER_AGENT


DEFAULT_INPUT = Path("data/characters.yaml")
DEFAULT_CONFIG = Path("data/fandom_wikis.yaml")
DEFAULT_REPORT = Path("data/fandom_image_report.yaml")
DEFAULT_THUMB_SIZE = 500
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_MIN_SCORE = 36
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
    "image_pageimage",
)
BLOCKED_IMAGE_TERMS = (
    "logo",
    "wordmark",
    "logotype",
    "title",
    "emblem",
    "symbol",
    "poster",
    "banner",
)
BLOCKED_PAGE_TERMS = (
    "/abilities",
    "/ability",
    "/appearance",
    "/battles",
    "/chapter",
    "/episode",
    "/family",
    "/gallery",
    "/history",
    "/image",
    "/misc",
    "/personality",
    "/relationships",
    "/synopsis",
    "/techniques",
)


def yaml_loader() -> type[yaml.Loader]:
    return getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def yaml_dumper() -> type[yaml.Dumper]:
    return getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=yaml_loader()) or {}


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        yaml.dump(
            data,
            handle,
            Dumper=yaml_dumper(),
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
    temp_path.replace(path)


def load_characters(path: Path) -> dict[str, Any]:
    data = load_yaml(path)
    if "characters" not in data or not isinstance(data["characters"], list):
        raise ValueError(f"{path} must contain a top-level 'characters' list")
    return data


def load_wiki_config(path: Path) -> dict[str, list[str]]:
    data = load_yaml(path)
    raw_wikis = data.get("wikis") if isinstance(data, dict) else None
    if not isinstance(raw_wikis, dict):
        raise ValueError(f"{path} must contain a top-level 'wikis' mapping")

    result: dict[str, list[str]] = {}
    for universe, hosts in raw_wikis.items():
        values = hosts if isinstance(hosts, list) else [hosts]
        normalized_hosts = [normalize_host(str(host)) for host in values if str(host).strip()]
        if normalized_hosts:
            result[str(universe)] = list(dict.fromkeys(normalized_hosts))
    return result


def load_alias_config(path: Path) -> dict[str, dict[str, list[str]]]:
    data = load_yaml(path)
    raw_aliases = data.get("aliases") if isinstance(data, dict) else None
    if not isinstance(raw_aliases, dict):
        return {}

    result: dict[str, dict[str, list[str]]] = {}
    for universe, alias_map in raw_aliases.items():
        if not isinstance(alias_map, dict):
            continue
        normalized_map: dict[str, list[str]] = {}
        for source_title, aliases in alias_map.items():
            values = aliases if isinstance(aliases, list) else [aliases]
            normalized_values = [str(value).strip() for value in values if str(value).strip()]
            if normalized_values:
                normalized_map[str(source_title)] = list(dict.fromkeys(normalized_values))
        if normalized_map:
            result[str(universe)] = normalized_map
    return result


def normalize_host(host: str) -> str:
    parsed = urlparse(host if "://" in host else f"https://{host}")
    return parsed.netloc.casefold().strip("/")


def request_json(url: str, *, timeout: int, user_agent: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fandom_api_url(host: str, params: dict[str, Any]) -> str:
    return f"https://{host}/api.php?{urlencode(params, quote_via=quote)}"


def title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    return unquote(path.rsplit("/", 1)[-1]).replace("_", " ").strip()


def strip_parenthetical(text: str) -> str:
    stripped = re.sub(r"\s*\([^)]*\)\s*", " ", text).strip()
    return re.sub(r"\s+", " ", stripped)


def ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", ascii_fold(text).casefold()).strip()


def text_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^0-9a-zA-Z]+", compact_text(text))
        if len(token) >= 3
    } - {
        "and",
        "anime",
        "character",
        "characters",
        "comic",
        "comics",
        "film",
        "from",
        "list",
        "manga",
        "movie",
        "the",
        "wiki",
    }


def title_candidates(
    character: dict[str, Any],
    aliases_by_universe: dict[str, dict[str, list[str]]] | None = None,
) -> list[str]:
    candidates: list[str] = []
    for key in ("source_name_original", "name"):
        value = character.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    original_title = title_from_url(str(character.get("source_wikipedia_url_original") or ""))
    if original_title:
        candidates.insert(0, original_title)
        stripped = strip_parenthetical(original_title)
        if stripped and stripped != original_title:
            candidates.insert(0, stripped)

    alias_candidates: list[str] = []
    universe = str(character.get("universe") or "")
    alias_map = (aliases_by_universe or {}).get(universe, {})
    compact_candidates = {compact_text(candidate) for candidate in candidates}
    for source_title, aliases in alias_map.items():
        if compact_text(source_title) in compact_candidates:
            alias_candidates.extend(aliases)

    folded: list[str] = []
    candidates = alias_candidates + candidates
    for candidate in candidates:
        folded.append(candidate)
        ascii_candidate = ascii_fold(candidate)
        if ascii_candidate != candidate:
            folded.append(ascii_candidate)

    return list(dict.fromkeys(value for value in folded if value))


def page_title_score(page_title: str, candidates: list[str]) -> int:
    normalized_title = compact_text(page_title)
    title_tokens = text_tokens(page_title)
    score = 0
    for candidate in candidates:
        normalized_candidate = compact_text(candidate)
        candidate_tokens = text_tokens(candidate)
        if not normalized_candidate:
            continue
        if normalized_title == normalized_candidate:
            score = max(score, 80)
        elif normalized_title.startswith(normalized_candidate):
            score = max(score, 58)
        elif normalized_candidate in normalized_title:
            score = max(score, 48)
        matched_tokens = title_tokens & candidate_tokens
        if candidate_tokens:
            score = max(score, len(matched_tokens) * 12)
            if len(matched_tokens) == len(candidate_tokens):
                score += 8

    lowered = normalized_title
    if any(term in lowered for term in BLOCKED_PAGE_TERMS):
        score -= 32
    if "list of" in lowered or "category:" in lowered:
        score -= 40
    if "/" in page_title and not any(compact_text(candidate) == normalized_title for candidate in candidates):
        score -= 18
    return score


def is_likely_non_character_image(filename: str) -> bool:
    normalized = filename.casefold()
    if normalized.endswith(".svg"):
        return True
    return any(term in normalized for term in BLOCKED_IMAGE_TERMS)


def page_image_from_record(page: dict[str, Any], *, host: str) -> dict[str, Any] | None:
    if page.get("missing") is not None or int(page.get("ns", 0)) != 0:
        return None
    pageimage = str(page.get("pageimage") or "")
    if pageimage and is_likely_non_character_image(pageimage):
        return None
    thumbnail = page.get("thumbnail") or {}
    original = page.get("original") or {}
    image_url = str(thumbnail.get("source") or original.get("source") or "")
    if not image_url:
        return None
    return {
        "host": host,
        "title": str(page.get("title") or ""),
        "pageid": page.get("pageid"),
        "page_url": str(page.get("fullurl") or page.get("canonicalurl") or ""),
        "image_url": image_url,
        "pageimage": pageimage,
        "width": thumbnail.get("width") or original.get("width"),
        "height": thumbnail.get("height") or original.get("height"),
    }


def fetch_page_images(
    host: str,
    titles: list[str],
    *,
    timeout: int,
    user_agent: str,
    thumb_size: int,
) -> list[dict[str, Any]]:
    if not titles:
        return []
    payload = request_json(
        fandom_api_url(
            host,
            {
                "action": "query",
                "format": "json",
                "prop": "pageimages|info",
                "piprop": "thumbnail|original|name",
                "pithumbsize": thumb_size,
                "inprop": "url",
                "redirects": 1,
                "titles": "|".join(titles[:50]),
            },
        ),
        timeout=timeout,
        user_agent=user_agent,
    )
    pages = payload.get("query", {}).get("pages", {})
    images: list[dict[str, Any]] = []
    for page in pages.values():
        if isinstance(page, dict):
            image = page_image_from_record(page, host=host)
            if image:
                images.append(image)
    return images


def search_pages(
    host: str,
    query: str,
    *,
    timeout: int,
    user_agent: str,
    search_limit: int,
) -> list[str]:
    payload = request_json(
        fandom_api_url(
            host,
            {
                "action": "query",
                "format": "json",
                "list": "search",
                "srnamespace": 0,
                "srlimit": search_limit,
                "srsearch": query,
            },
        ),
        timeout=timeout,
        user_agent=user_agent,
    )
    titles: list[str] = []
    for row in payload.get("query", {}).get("search", []) or []:
        if isinstance(row, dict) and row.get("title"):
            titles.append(str(row["title"]))
    return titles


def best_image_for_host(
    character: dict[str, Any],
    host: str,
    *,
    aliases_by_universe: dict[str, dict[str, list[str]]],
    timeout: int,
    user_agent: str,
    thumb_size: int,
    search_limit: int,
    min_score: int,
    sleep_seconds: float,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    candidates = title_candidates(character, aliases_by_universe)
    attempts: list[dict[str, Any]] = []

    try:
        exact_images = fetch_page_images(
            host,
            candidates[:8],
            timeout=timeout,
            user_agent=user_agent,
            thumb_size=thumb_size,
        )
    except Exception as exc:
        attempts.append({"host": host, "stage": "exact", "error": f"{type(exc).__name__}: {exc}"})
        exact_images = []

    best_image: dict[str, Any] | None = None
    best_score = -100
    for image in exact_images:
        score = page_title_score(str(image.get("title") or ""), candidates)
        attempts.append({"host": host, "stage": "exact", "title": image.get("title"), "score": score})
        if score > best_score:
            best_image = image
            best_score = score

    if best_image and best_score >= min_score:
        best_image["_match_score"] = best_score
        return best_image, attempts

    search_titles: list[str] = []
    for query in candidates[:4]:
        try:
            search_titles.extend(
                search_pages(
                    host,
                    query,
                    timeout=timeout,
                    user_agent=user_agent,
                    search_limit=search_limit,
                )
            )
        except Exception as exc:
            attempts.append({"host": host, "stage": "search", "query": query, "error": f"{type(exc).__name__}: {exc}"})
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    ranked_titles = sorted(
        set(search_titles),
        key=lambda title: page_title_score(title, candidates),
        reverse=True,
    )
    try:
        search_images = fetch_page_images(
            host,
            ranked_titles[:8],
            timeout=timeout,
            user_agent=user_agent,
            thumb_size=thumb_size,
        )
    except Exception as exc:
        attempts.append({"host": host, "stage": "search-images", "error": f"{type(exc).__name__}: {exc}"})
        search_images = []

    for image in search_images:
        score = page_title_score(str(image.get("title") or ""), candidates)
        attempts.append({"host": host, "stage": "search", "title": image.get("title"), "score": score})
        if score > best_score:
            best_image = image
            best_score = score

    if not best_image or best_score < min_score:
        return None, attempts
    best_image["_match_score"] = best_score
    return best_image, attempts


def fandom_credit(host: str) -> str:
    wiki_name = host.removesuffix(".fandom.com").replace("-", " ").replace(".", " ")
    return f"{wiki_name.title()} Fandom"


def apply_image(character: dict[str, Any], image: dict[str, Any]) -> None:
    for field in IMAGE_FIELDS:
        character.pop(field, None)
    host = str(image.get("host") or "")
    character["image_url"] = str(image["image_url"])
    character["image_source"] = f"fandom:{host}"
    character["image_alt"] = str(character.get("name") or image.get("title") or "")
    character["image_landing_url"] = str(image.get("page_url") or "")
    character["image_credit"] = fandom_credit(host)
    if image.get("pageimage"):
        character["image_pageimage"] = str(image["pageimage"])


def update_characters(
    data: dict[str, Any],
    *,
    wikis_by_universe: dict[str, list[str]],
    aliases_by_universe: dict[str, dict[str, list[str]]],
    timeout: int,
    user_agent: str,
    thumb_size: int,
    search_limit: int,
    sleep_seconds: float,
    limit: int | None,
    min_score: int,
    overwrite_existing: bool,
    dry_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    characters = data["characters"]
    missing_before = sum(1 for character in characters if not character.get("image_url"))
    candidates = [
        character
        for character in characters
        if (overwrite_existing or not character.get("image_url"))
        and str(character.get("universe") or "") in wikis_by_universe
    ]
    if limit is not None:
        candidates = candidates[:limit]

    found_items: list[dict[str, Any]] = []
    missing_items: list[dict[str, Any]] = []
    skipped_no_wiki = [
        {"name": character.get("name"), "universe": character.get("universe")}
        for character in characters
        if (overwrite_existing or not character.get("image_url"))
        and str(character.get("universe") or "") not in wikis_by_universe
    ]

    for character in candidates:
        universe = str(character.get("universe") or "")
        all_attempts: list[dict[str, Any]] = []
        selected_image: dict[str, Any] | None = None
        for host in wikis_by_universe[universe]:
            image, attempts = best_image_for_host(
                character,
                host,
                aliases_by_universe=aliases_by_universe,
                timeout=timeout,
                user_agent=user_agent,
                thumb_size=thumb_size,
                search_limit=search_limit,
                min_score=min_score,
                sleep_seconds=sleep_seconds,
            )
            all_attempts.extend(attempts)
            if image:
                selected_image = image
                break
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        if selected_image:
            if not dry_run:
                apply_image(character, selected_image)
            found_items.append(
                {
                    "name": character.get("name"),
                    "universe": universe,
                    "host": selected_image.get("host"),
                    "title": selected_image.get("title"),
                    "page_url": selected_image.get("page_url"),
                    "image_url": selected_image.get("image_url"),
                    "pageimage": selected_image.get("pageimage"),
                    "score": selected_image.get("_match_score"),
                }
            )
        else:
            missing_items.append(
                {
                    "name": character.get("name"),
                    "universe": universe,
                    "title_candidates": title_candidates(character, aliases_by_universe)[:6],
                    "attempts": all_attempts[:10],
                }
            )

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    source_counts = Counter(str(item.get("host") or "unknown") for item in found_items)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Fandom configured MediaWiki APIs",
        "dry_run": dry_run,
        "total_characters": len(characters),
        "characters_without_images_before": missing_before,
        "candidates_checked": len(candidates),
        "images_found": len(found_items),
        "characters_without_images_after": (
            missing_before if dry_run else sum(1 for character in characters if not character.get("image_url"))
        ),
        "overwrite_existing": overwrite_existing,
        "configured_universes": len(wikis_by_universe),
        "min_score": min_score,
        "source_counts": dict(source_counts),
        "items": found_items,
        "missing_items": missing_items,
        "skipped_no_wiki": skipped_no_wiki,
    }
    return data, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Fandom thumbnails for display.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--thumb-size", type=int, default=DEFAULT_THUMB_SIZE)
    parser.add_argument("--search-limit", type=int, default=DEFAULT_SEARCH_LIMIT)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--overwrite-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_characters(args.input)
    wikis_by_universe = load_wiki_config(args.config)
    aliases_by_universe = load_alias_config(args.config)
    updated_data, report = update_characters(
        data,
        wikis_by_universe=wikis_by_universe,
        aliases_by_universe=aliases_by_universe,
        timeout=args.timeout,
        user_agent=args.user_agent,
        thumb_size=args.thumb_size,
        search_limit=args.search_limit,
        sleep_seconds=args.sleep,
        limit=args.limit,
        min_score=args.min_score,
        overwrite_existing=args.overwrite_existing,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        save_yaml(args.output, updated_data)
    save_yaml(args.report, report)


if __name__ == "__main__":
    main()
