"""Fetch display thumbnails from Japanese Wikipedia pageimages.

Images are presentation metadata only. They are not used for scoring, feature
extraction, ranking, or battle comparison.
"""

from __future__ import annotations

import argparse
import json
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
                    }

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    return result


def is_likely_non_character_image(pageimage: str) -> bool:
    normalized = pageimage.casefold()
    blocked_terms = [
        "logo",
        "wordmark",
        "logotype",
        "title",
    ]
    if normalized.endswith(".svg"):
        return True
    return any(term in normalized for term in blocked_terms)


def clear_image_fields(character: dict[str, Any]) -> None:
    for key in ("image_url", "image_source", "image_alt", "image_pageimage"):
        character.pop(key, None)


def update_characters(
    data: dict[str, Any],
    *,
    timeout: int,
    user_agent: str,
    thumb_size: int,
    batch_size: int,
    sleep_seconds: float,
    include_shared: bool,
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

    found_items: list[dict[str, Any]] = []
    missing_items: list[dict[str, Any]] = []
    for character in characters:
        url = str(character.get("wikipedia_url") or "")
        image = images.get(url)
        if not image:
            if not any(item["name"] == character.get("name") and item["url"] == url for item in skipped_shared):
                missing_items.append({"name": character.get("name"), "url": url})
            continue
        character["image_url"] = image["image_url"]
        character["image_source"] = "ja.wikipedia.org pageimages"
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
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_characters": len(characters),
        "candidate_pages": len(candidates),
        "images_found": len(found_items),
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
    )
    save_yaml(args.output, updated_data)
    save_yaml(args.report, report)


if __name__ == "__main__":
    main()
