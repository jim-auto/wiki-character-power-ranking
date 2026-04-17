"""Fetch plain-text Wikipedia extracts for character records.

The fetcher intentionally stores only Wikipedia text. It does not follow
non-Wikipedia sources and it does not enrich the data with outside knowledge.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

import yaml


DEFAULT_INPUT = Path("data/characters.yaml")
DEFAULT_USER_AGENT = (
    "wiki-character-power-index/0.1 "
    "(educational prototype; uses Wikipedia text only)"
)


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


def parse_wikipedia_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if not parsed.netloc.endswith("wikipedia.org"):
        raise ValueError(f"Not a Wikipedia URL: {url}")

    if parsed.path.startswith("/wiki/"):
        title = unquote(parsed.path.removeprefix("/wiki/")).replace("_", " ")
        if title:
            return parsed.netloc, title

    query_title = parse_qs(parsed.query).get("title", [""])[0]
    if query_title:
        return parsed.netloc, unquote(query_title).replace("_", " ")

    raise ValueError(f"Could not infer page title from URL: {url}")


def build_api_url(host: str, title: str, intro_only: bool) -> str:
    params: dict[str, str | int] = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "explaintext": 1,
        "redirects": 1,
        "titles": title,
    }
    if intro_only:
        params["exintro"] = 1
    return f"https://{host}/w/api.php?{urlencode(params, quote_via=quote)}"


def fetch_extract(
    wikipedia_url: str,
    *,
    intro_only: bool = False,
    timeout: int = 20,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    host, title = parse_wikipedia_url(wikipedia_url)
    request = Request(
        build_api_url(host, title, intro_only),
        headers={"User-Agent": user_agent},
    )

    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    pages = payload.get("query", {}).get("pages", {})
    if not pages:
        raise ValueError(f"Wikipedia returned no pages for {wikipedia_url}")

    page = next(iter(pages.values()))
    if "missing" in page:
        raise ValueError(f"Wikipedia page is missing: {wikipedia_url}")

    extract = (page.get("extract") or "").strip()
    if not extract:
        raise ValueError(f"Wikipedia page has an empty extract: {wikipedia_url}")

    return {
        "extract": extract,
        "title": page.get("title", title),
        "pageid": page.get("pageid"),
        "revision_id": page.get("lastrevid"),
        "language_host": host,
    }


def update_characters(
    data: dict[str, Any],
    *,
    intro_only: bool,
    timeout: int,
    sleep_seconds: float,
    user_agent: str,
) -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()

    for character in data["characters"]:
        url = character.get("wikipedia_url")
        if not url:
            raise ValueError(f"Character is missing wikipedia_url: {character!r}")

        page = fetch_extract(
            url,
            intro_only=intro_only,
            timeout=timeout,
            user_agent=user_agent,
        )
        character["description_raw"] = page["extract"]
        character["source_metadata"] = {
            "wikipedia_title": page["title"],
            "pageid": page["pageid"],
            "revision_id": page["revision_id"],
            "language_host": page["language_host"],
            "fetched_at": fetched_at,
            "intro_only": intro_only,
        }

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Wikipedia extracts into data/characters.yaml."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--intro-only",
        action="store_true",
        help="Fetch only the lead section instead of the full page extract.",
    )
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    updated = update_characters(
        data,
        intro_only=args.intro_only,
        timeout=args.timeout,
        sleep_seconds=args.sleep,
        user_agent=args.user_agent,
    )
    save_yaml(args.output, updated)


if __name__ == "__main__":
    main()
