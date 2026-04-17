"""Fetch display thumbnails from Japanese Wikipedia pageimages.

Images are presentation metadata only. They are not used for scoring, feature
extraction, ranking, or battle comparison.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import yaml

from fetch_wikipedia import DEFAULT_USER_AGENT, build_title_aliases, parse_wikipedia_url, resolve_title


DEFAULT_INPUT = Path("data/characters.yaml")
DEFAULT_REPORT = Path("data/image_fetch_report.yaml")
COMMONS_SEARCH_LIMIT = 10
COMMONS_SEARCH_MIN_SCORE = 18


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


def base_wikipedia_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def request_json(url: str, *, timeout: int, user_agent: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_pageimages_url(host: str, titles: list[str], thumb_size: int) -> str:
    return f"https://{host}/w/api.php?{urlencode({
        'action': 'query',
        'format': 'json',
        'prop': 'pageimages',
        'piprop': 'thumbnail|name',
        'pithumbsize': thumb_size,
        'redirects': 1,
        'titles': '|'.join(titles),
    }, quote_via=quote)}"


def build_pageprops_url(host: str, titles: list[str]) -> str:
    return f"https://{host}/w/api.php?{urlencode({
        'action': 'query',
        'format': 'json',
        'prop': 'pageprops',
        'redirects': 1,
        'titles': '|'.join(titles),
    }, quote_via=quote)}"


def build_wikidata_entities_url(
    qids: list[str],
    *,
    props: str = "claims",
    languages: str | None = None,
) -> str:
    params = {
        'action': 'wbgetentities',
        'format': 'json',
        'ids': '|'.join(qids),
        'props': props,
    }
    if languages:
        params["languages"] = languages
    return f"https://www.wikidata.org/w/api.php?{urlencode(params, quote_via=quote)}"


def build_commons_imageinfo_url(filenames: list[str], thumb_size: int) -> str:
    titles = [f"File:{filename}" for filename in filenames]
    return f"https://commons.wikimedia.org/w/api.php?{urlencode({
        'action': 'query',
        'format': 'json',
        'prop': 'imageinfo',
        'iiprop': 'url',
        'iiurlwidth': thumb_size,
        'titles': '|'.join(titles),
    }, quote_via=quote)}"


def build_commons_search_url(query: str, limit: int) -> str:
    return f"https://commons.wikimedia.org/w/api.php?{urlencode({
        'action': 'query',
        'format': 'json',
        'list': 'search',
        'srnamespace': 6,
        'srlimit': limit,
        'srsearch': query,
    }, quote_via=quote)}"


def fetch_pageimages(
    url_title_pairs: list[tuple[str, str, str]],
    *,
    timeout: int,
    user_agent: str,
    thumb_size: int,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    by_host: dict[str, list[tuple[str, str]]] = {}
    for url, host, title in url_title_pairs:
        by_host.setdefault(host, []).append((url, title))

    for host, pairs in by_host.items():
        for batch in chunked(pairs, batch_size):
            titles = [title for _url, title in batch]
            payload = request_json(
                build_pageimages_url(host, titles, thumb_size),
                timeout=timeout,
                user_agent=user_agent,
            )
            aliases = build_title_aliases(payload)
            pages = payload.get("query", {}).get("pages", {})
            pages_by_title = {str(page.get("title")): page for page in pages.values()}

            for url, title in batch:
                resolved_title = resolve_title(title, aliases)
                page = pages_by_title.get(resolved_title) or pages_by_title.get(title)
                if not page:
                    continue
                thumbnail = (page.get("thumbnail") or {}).get("source")
                pageimage = str(page.get("pageimage") or "")
                if thumbnail and not is_likely_non_character_image(pageimage):
                    result[url] = {
                        "image_url": str(thumbnail),
                        "pageimage": pageimage,
                        "wikipedia_title": page.get("title", title),
                        "source": "ja.wikipedia.org pageimages",
                    }

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    return result


def fetch_wikidata_items(
    url_title_pairs: list[tuple[str, str, str]],
    *,
    timeout: int,
    user_agent: str,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    by_host: dict[str, list[tuple[str, str]]] = {}
    for url, host, title in url_title_pairs:
        by_host.setdefault(host, []).append((url, title))

    for host, pairs in by_host.items():
        for batch in chunked(pairs, batch_size):
            titles = [title for _url, title in batch]
            payload = request_json(
                build_pageprops_url(host, titles),
                timeout=timeout,
                user_agent=user_agent,
            )
            aliases = build_title_aliases(payload)
            pages = payload.get("query", {}).get("pages", {})
            pages_by_title = {str(page.get("title")): page for page in pages.values()}

            for url, title in batch:
                resolved_title = resolve_title(title, aliases)
                page = pages_by_title.get(resolved_title) or pages_by_title.get(title)
                if not page:
                    continue
                qid = (page.get("pageprops") or {}).get("wikibase_item")
                if qid:
                    result[url] = {
                        "qid": str(qid),
                        "wikipedia_title": str(page.get("title", title)),
                    }

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    return result


def fetch_wikidata_p18_filenames(
    qids: list[str],
    *,
    timeout: int,
    user_agent: str,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for batch in chunked(qids, batch_size):
        payload = request_json(
            build_wikidata_entities_url(batch),
            timeout=timeout,
            user_agent=user_agent,
        )
        entities = payload.get("entities", {})
        for qid in batch:
            claims = (entities.get(qid) or {}).get("claims", {})
            for claim in claims.get("P18", []) or []:
                filename = (
                    claim.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value")
                )
                if isinstance(filename, str) and not is_likely_non_character_image(filename):
                    result[qid] = filename
                    break

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return result


def claim_string_values(claims: dict[str, Any], property_id: str) -> list[str]:
    values: list[str] = []
    for claim in claims.get(property_id, []) or []:
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str):
            values.append(value)
    return values


def normalize_commons_category(category: str) -> str:
    if category.startswith("Category:"):
        return category.removeprefix("Category:").strip()
    return category.strip()


def fetch_wikidata_image_metadata(
    qids: list[str],
    *,
    timeout: int,
    user_agent: str,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for batch in chunked(qids, batch_size):
        payload = request_json(
            build_wikidata_entities_url(batch, props="claims|labels|sitelinks", languages="ja|en"),
            timeout=timeout,
            user_agent=user_agent,
        )
        entities = payload.get("entities", {})
        for qid in batch:
            entity = entities.get(qid) or {}
            claims = entity.get("claims", {})
            labels = entity.get("labels", {})
            categories = [
                normalize_commons_category(category)
                for category in claim_string_values(claims, "P373")
            ]
            commons_title = (entity.get("sitelinks", {}).get("commonswiki") or {}).get("title")
            if isinstance(commons_title, str) and commons_title.startswith("Category:"):
                categories.append(normalize_commons_category(commons_title))
            result[qid] = {
                "p18_filenames": [
                    filename
                    for filename in claim_string_values(claims, "P18")
                    if not is_likely_non_character_image(filename)
                ],
                "commons_categories": sorted(set(category for category in categories if category)),
                "labels": {
                    language: str(value.get("value"))
                    for language, value in labels.items()
                    if isinstance(value, dict) and value.get("value")
                },
            }

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return result


def fetch_commons_thumbnails(
    filenames: list[str],
    *,
    timeout: int,
    user_agent: str,
    thumb_size: int,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for batch in chunked(filenames, batch_size):
        payload = request_json(
            build_commons_imageinfo_url(batch, thumb_size),
            timeout=timeout,
            user_agent=user_agent,
        )
        pages = payload.get("query", {}).get("pages", {})
        by_title = {str(page.get("title")): page for page in pages.values()}

        for filename in batch:
            page = by_title.get(f"File:{filename}")
            if not page:
                continue
            imageinfo = (page.get("imageinfo") or [{}])[0]
            image_url = imageinfo.get("thumburl") or imageinfo.get("url")
            if image_url:
                result[filename] = {
                    "image_url": str(image_url),
                    "pageimage": filename,
                }

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return result


def filename_from_file_title(title: str) -> str | None:
    if not title.startswith("File:"):
        return None
    filename = title.removeprefix("File:").strip()
    if not filename or is_likely_non_character_image(filename):
        return None
    return filename


def text_tokens(text: str) -> set[str]:
    lowered = text.casefold()
    tokens = {
        token
        for token in re.split(r"[^0-9a-zA-Z]+", lowered)
        if len(token) >= 3
    }
    return tokens - {
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
    }


def score_commons_filename(filename: str, contexts: list[str]) -> int:
    normalized = filename.casefold()
    if is_likely_non_character_image(filename):
        return -100

    score = 0
    if any(term in normalized for term in ("cosplay", "cosplayer", "costume")):
        score += 20
    if any(term in normalized for term in ("booth", "paper bag", "paper_bag", "t-shirt", "t_shirt")):
        score -= 12

    tokens: set[str] = set()
    for context in contexts:
        tokens.update(text_tokens(context))
    matched_tokens = [token for token in tokens if token in normalized]
    score += len(matched_tokens) * 5
    if len(matched_tokens) >= 2:
        score += 5
    return score


def search_queries_for_metadata(metadata: dict[str, Any]) -> tuple[list[str], list[str]]:
    contexts: list[str] = []
    labels = metadata.get("labels") or {}
    for language in ("en", "ja"):
        label = labels.get(language)
        if label:
            contexts.append(str(label))
    contexts.extend(str(category) for category in metadata.get("commons_categories") or [])

    queries: list[str] = []
    for context in contexts:
        text = normalize_commons_category(context)
        if not text:
            continue
        if "(" in text and ")" in text:
            base, remainder = text.split("(", 1)
            detail = remainder.split(")", 1)[0]
            if base.strip() and detail.strip():
                queries.append(f'"{base.strip()}" "{detail.strip()}" cosplay')
        queries.append(f'"{text}" cosplay')

    return list(dict.fromkeys(queries)), list(dict.fromkeys(contexts))


def fetch_commons_search_filenames(
    metadata_by_qid: dict[str, dict[str, Any]],
    *,
    timeout: int,
    user_agent: str,
    sleep_seconds: float,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for qid, metadata in metadata_by_qid.items():
        queries, contexts = search_queries_for_metadata(metadata)
        best_filename: str | None = None
        best_score = -100
        for query in queries:
            payload = request_json(
                build_commons_search_url(query, COMMONS_SEARCH_LIMIT),
                timeout=timeout,
                user_agent=user_agent,
            )
            for row in payload.get("query", {}).get("search", []) or []:
                filename = filename_from_file_title(str(row.get("title") or ""))
                if not filename:
                    continue
                score = score_commons_filename(filename, contexts)
                if score > best_score:
                    best_filename = filename
                    best_score = score

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

        if best_filename and best_score >= COMMONS_SEARCH_MIN_SCORE:
            result[qid] = best_filename

    return result


def fetch_wikidata_images(
    url_title_pairs: list[tuple[str, str, str]],
    *,
    timeout: int,
    user_agent: str,
    thumb_size: int,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, dict[str, Any]]:
    wikidata_items = fetch_wikidata_items(
        url_title_pairs,
        timeout=timeout,
        user_agent=user_agent,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    qids = sorted({item["qid"] for item in wikidata_items.values()})
    filenames_by_qid = fetch_wikidata_p18_filenames(
        qids,
        timeout=timeout,
        user_agent=user_agent,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    filenames = sorted(set(filenames_by_qid.values()))
    commons_images = fetch_commons_thumbnails(
        filenames,
        timeout=timeout,
        user_agent=user_agent,
        thumb_size=thumb_size,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )

    result: dict[str, dict[str, Any]] = {}
    for url, item in wikidata_items.items():
        qid = item["qid"]
        filename = filenames_by_qid.get(qid)
        if not filename:
            continue
        image = commons_images.get(filename)
        if not image:
            continue
        result[url] = {
            "image_url": image["image_url"],
            "pageimage": filename,
            "wikidata_item": qid,
            "wikipedia_title": item["wikipedia_title"],
            "source": "wikidata P18 via ja.wikipedia.org pageprops",
        }
    return result


def fetch_source_wikidata_images(
    qids: list[str],
    *,
    commons_search_qids: set[str],
    timeout: int,
    user_agent: str,
    thumb_size: int,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, dict[str, Any]]:
    metadata_by_qid = fetch_wikidata_image_metadata(
        qids,
        timeout=timeout,
        user_agent=user_agent,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    p18_filenames_by_qid: dict[str, str] = {}
    for qid, metadata in metadata_by_qid.items():
        filenames = metadata.get("p18_filenames") or []
        if filenames:
            p18_filenames_by_qid[qid] = str(filenames[0])

    p18_commons_images = fetch_commons_thumbnails(
        sorted(set(p18_filenames_by_qid.values())),
        timeout=timeout,
        user_agent=user_agent,
        thumb_size=thumb_size,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )

    result: dict[str, dict[str, Any]] = {}
    for qid, filename in p18_filenames_by_qid.items():
        image = p18_commons_images.get(filename)
        if not image:
            continue
        result[qid] = {
            "image_url": image["image_url"],
            "pageimage": filename,
            "wikidata_item": qid,
            "source": "wikidata P18 via character_wikidata_id",
        }

    remaining_metadata = {
        qid: metadata
        for qid, metadata in metadata_by_qid.items()
        if qid not in result and qid in commons_search_qids and metadata.get("commons_categories")
    }
    search_filenames_by_qid = fetch_commons_search_filenames(
        remaining_metadata,
        timeout=timeout,
        user_agent=user_agent,
        sleep_seconds=sleep_seconds,
    )
    search_commons_images = fetch_commons_thumbnails(
        sorted(set(search_filenames_by_qid.values())),
        timeout=timeout,
        user_agent=user_agent,
        thumb_size=thumb_size,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    for qid, filename in search_filenames_by_qid.items():
        image = search_commons_images.get(filename)
        if not image:
            continue
        result[qid] = {
            "image_url": image["image_url"],
            "pageimage": filename,
            "wikidata_item": qid,
            "source": "commons search via character_wikidata_id",
        }
    return result


def is_likely_non_character_image(pageimage: str) -> bool:
    normalized = pageimage.casefold()
    blocked_terms = [
        "logo",
        "wordmark",
        "logotype",
        "title",
        "emblem",
        "symbol",
    ]
    if normalized.endswith(".svg"):
        return True
    return any(term in normalized for term in blocked_terms)


def clear_image_fields(character: dict[str, Any]) -> None:
    for key in ("image_url", "image_source", "image_alt", "image_pageimage"):
        character.pop(key, None)


def character_image_wikidata_id(character: dict[str, Any]) -> str:
    return str(character.get("image_wikidata_id") or character.get("source_wikidata_id") or "")


def update_characters(
    data: dict[str, Any],
    *,
    timeout: int,
    user_agent: str,
    thumb_size: int,
    batch_size: int,
    sleep_seconds: float,
    include_shared: bool,
    wikidata_fallback: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    characters = data["characters"]
    base_counts = Counter(base_wikipedia_url(str(character.get("wikipedia_url") or "")) for character in characters)
    candidates: list[tuple[str, str, str]] = []
    skipped_shared: list[dict[str, Any]] = []

    for character in characters:
        clear_image_fields(character)
        url = str(character.get("wikipedia_url") or "")
        base_url = base_wikipedia_url(url)
        if not include_shared and base_counts[base_url] > 1:
            skipped_shared.append({"name": character.get("name"), "url": url})
            continue
        host, title = parse_wikipedia_url(url)
        if host != "ja.wikipedia.org":
            continue
        candidates.append((url, host, title))

    images = fetch_pageimages(
        candidates,
        timeout=timeout,
        user_agent=user_agent,
        thumb_size=thumb_size,
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    pageimage_count = len(images)

    wikidata_count = 0
    source_wikidata_images: dict[str, dict[str, Any]] = {}
    if wikidata_fallback:
        fallback_candidates = [candidate for candidate in candidates if candidate[0] not in images]
        wikidata_images = fetch_wikidata_images(
            fallback_candidates,
            timeout=timeout,
            user_agent=user_agent,
            thumb_size=thumb_size,
            batch_size=batch_size,
            sleep_seconds=sleep_seconds,
        )
        wikidata_count = len(wikidata_images)
        images.update(wikidata_images)
        source_qids = sorted(
            {
                character_image_wikidata_id(character)
                for character in characters
                if character_image_wikidata_id(character)
                and str(character.get("wikipedia_url") or "") not in images
            }
        )
        commons_search_qids = {
            str(character.get("image_wikidata_id"))
            for character in characters
            if character.get("image_wikidata_id")
        }
        source_wikidata_images = fetch_source_wikidata_images(
            source_qids,
            commons_search_qids=commons_search_qids,
            timeout=timeout,
            user_agent=user_agent,
            thumb_size=thumb_size,
            batch_size=batch_size,
            sleep_seconds=sleep_seconds,
        )

    found_items: list[dict[str, Any]] = []
    missing_items: list[dict[str, Any]] = []
    source_wikidata_count = 0
    for character in characters:
        url = str(character.get("wikipedia_url") or "")
        image = images.get(url)
        if not image:
            qid = character_image_wikidata_id(character)
            image = source_wikidata_images.get(qid)
            if image:
                source_wikidata_count += 1
        if not image:
            if not any(item["name"] == character.get("name") and item["url"] == url for item in skipped_shared):
                missing_items.append({"name": character.get("name"), "url": url})
            continue
        character["image_url"] = image["image_url"]
        character["image_source"] = image["source"]
        character["image_alt"] = str(character.get("name") or "")
        if image.get("pageimage"):
            character["image_pageimage"] = image["pageimage"]
        found_items.append(
            {
                "name": character.get("name"),
                "url": url,
                "image_url": image["image_url"],
                "pageimage": image.get("pageimage"),
                "wikipedia_title": image.get("wikipedia_title"),
                "source": image.get("source"),
                "wikidata_item": image.get("wikidata_item"),
            }
        )

    source_counts = Counter(str(item.get("source") or "unknown") for item in found_items)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_characters": len(characters),
        "candidate_pages": len(candidates),
        "images_found": len(found_items),
        "characters_without_images": sum(1 for character in characters if not character.get("image_url")),
        "pageimage_images_found": pageimage_count,
        "wikidata_images_found": wikidata_count,
        "source_wikidata_images_found": source_wikidata_count,
        "source_counts": dict(source_counts),
        "missing_images": len(missing_items),
        "skipped_shared_pages": len(skipped_shared),
        "items": found_items,
        "missing_items": missing_items,
        "skipped_shared_items": skipped_shared,
    }
    return data, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Japanese Wikipedia thumbnails for display.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--thumb-size", type=int, default=360)
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--include-shared", action="store_true")
    parser.add_argument(
        "--no-wikidata-fallback",
        action="store_false",
        dest="wikidata_fallback",
        help="Disable Commons thumbnails from Wikidata P18 linked through Japanese Wikipedia pageprops.",
    )
    parser.set_defaults(wikidata_fallback=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    updated_data, report = update_characters(
        data,
        timeout=args.timeout,
        user_agent=args.user_agent,
        thumb_size=args.thumb_size,
        batch_size=args.batch_size,
        sleep_seconds=args.sleep,
        include_shared=args.include_shared,
        wikidata_fallback=args.wikidata_fallback,
    )
    save_yaml(args.output, updated_data)
    save_yaml(args.report, report)


if __name__ == "__main__":
    main()
