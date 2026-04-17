"""Fetch plain-text Wikipedia extracts for character records.

The fetcher intentionally stores only Wikipedia text. It does not follow
non-Wikipedia sources and it does not enrich the data with outside knowledge.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.error import HTTPError, URLError
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
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            data,
            handle,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
    temp_path.replace(path)


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


def build_summary_url(host: str, title: str) -> str:
    slug = quote(title.replace(" ", "_"), safe="")
    return f"https://{host}/api/rest_v1/page/summary/{slug}"


def build_html_url(host: str, title: str) -> str:
    slug = quote(title.replace(" ", "_"), safe="")
    return f"https://{host}/api/rest_v1/page/html/{slug}"


def request_json(
    api_url: str,
    *,
    timeout: int,
    user_agent: str,
    retries: int,
    retry_sleep: float,
) -> dict[str, Any]:
    request = Request(api_url, headers={"User-Agent": user_agent})
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        sleep_for = retry_sleep * (attempt + 1)
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if exc.code == 429:
                sleep_for = max(sleep_for, retry_after_seconds(exc))
            if not retryable or attempt >= retries:
                raise
        except URLError as exc:
            last_error = exc
            if attempt >= retries:
                raise

        time.sleep(sleep_for)

    raise RuntimeError(f"Could not fetch {api_url}: {last_error}")


def request_text(
    api_url: str,
    *,
    timeout: int,
    user_agent: str,
    retries: int,
    retry_sleep: float,
) -> str:
    request = Request(api_url, headers={"User-Agent": user_agent})
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        sleep_for = retry_sleep * (attempt + 1)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            last_error = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if exc.code == 429:
                sleep_for = max(sleep_for, retry_after_seconds(exc))
            if not retryable or attempt >= retries:
                raise
        except URLError as exc:
            last_error = exc
            if attempt >= retries:
                raise

        time.sleep(sleep_for)

    raise RuntimeError(f"Could not fetch {api_url}: {last_error}")


def retry_after_seconds(error: HTTPError) -> float:
    value = error.headers.get("Retry-After")
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0


class WikipediaHtmlTextExtractor(HTMLParser):
    block_tags = {"p", "li", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "br"}
    skip_tags = {
        "figure",
        "footer",
        "header",
        "math",
        "meta",
        "nav",
        "script",
        "style",
        "sup",
        "table",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line).strip()


def fetch_extract(
    wikipedia_url: str,
    *,
    intro_only: bool = False,
    timeout: int = 20,
    user_agent: str = DEFAULT_USER_AGENT,
    retries: int = 3,
    retry_sleep: float = 2.0,
) -> dict[str, Any]:
    host, title = parse_wikipedia_url(wikipedia_url)
    payload = request_json(
        build_api_url(host, title, intro_only),
        timeout=timeout,
        user_agent=user_agent,
        retries=retries,
        retry_sleep=retry_sleep,
    )

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


def build_title_aliases(payload: dict[str, Any]) -> dict[str, str]:
    query = payload.get("query", {})
    aliases: dict[str, str] = {}

    for item in query.get("normalized", []) or []:
        if item.get("from") and item.get("to"):
            aliases[str(item["from"])] = str(item["to"])

    for item in query.get("redirects", []) or []:
        if item.get("from") and item.get("to"):
            aliases[str(item["from"])] = str(item["to"])

    return aliases


def resolve_title(title: str, aliases: dict[str, str]) -> str:
    current = title
    for _ in range(4):
        next_title = aliases.get(current)
        if not next_title or next_title == current:
            return current
        current = next_title
    return current


def fetch_extracts(
    wikipedia_urls: list[str],
    *,
    intro_only: bool = False,
    timeout: int = 20,
    user_agent: str = DEFAULT_USER_AGENT,
    retries: int = 3,
    retry_sleep: float = 2.0,
) -> list[dict[str, Any]]:
    parsed = [parse_wikipedia_url(url) for url in wikipedia_urls]
    hosts = {host for host, _title in parsed}
    if len(hosts) != 1:
        raise ValueError("fetch_extracts requires URLs from one Wikipedia host per batch")

    host = parsed[0][0]
    titles = [title for _host, title in parsed]
    payload = request_json(
        build_api_url(host, "|".join(titles), intro_only),
        timeout=timeout,
        user_agent=user_agent,
        retries=retries,
        retry_sleep=retry_sleep,
    )

    pages = payload.get("query", {}).get("pages", {})
    if not pages:
        raise ValueError("Wikipedia returned no pages for batch")

    title_aliases = build_title_aliases(payload)
    pages_by_title = {str(page.get("title")): page for page in pages.values()}
    results: list[dict[str, Any]] = []

    for url, (_host, title) in zip(wikipedia_urls, parsed):
        resolved_title = resolve_title(title, title_aliases)
        page = pages_by_title.get(resolved_title) or pages_by_title.get(title)
        if not page:
            raise ValueError(f"Wikipedia returned no page for {url}")
        if "missing" in page:
            raise ValueError(f"Wikipedia page is missing: {url}")

        extract = (page.get("extract") or "").strip()
        if not extract:
            raise ValueError(f"Wikipedia page has an empty extract: {url}")

        results.append(
            {
                "extract": extract,
                "title": page.get("title", title),
                "pageid": page.get("pageid"),
                "revision_id": page.get("lastrevid"),
                "language_host": host,
            }
        )

    return results


def fetch_summary(
    wikipedia_url: str,
    *,
    timeout: int = 20,
    user_agent: str = DEFAULT_USER_AGENT,
    retries: int = 3,
    retry_sleep: float = 2.0,
) -> dict[str, Any]:
    host, title = parse_wikipedia_url(wikipedia_url)
    payload = request_json(
        build_summary_url(host, title),
        timeout=timeout,
        user_agent=user_agent,
        retries=retries,
        retry_sleep=retry_sleep,
    )

    extract = (payload.get("extract") or "").strip()
    if not extract:
        raise ValueError(f"Wikipedia summary has an empty extract: {wikipedia_url}")

    return {
        "extract": extract,
        "title": payload.get("title", title),
        "pageid": payload.get("pageid"),
        "revision_id": payload.get("revision"),
        "language_host": host,
    }


def fetch_html_extract(
    wikipedia_url: str,
    *,
    timeout: int = 20,
    user_agent: str = DEFAULT_USER_AGENT,
    retries: int = 3,
    retry_sleep: float = 2.0,
) -> dict[str, Any]:
    host, title = parse_wikipedia_url(wikipedia_url)
    html = request_text(
        build_html_url(host, title),
        timeout=timeout,
        user_agent=user_agent,
        retries=retries,
        retry_sleep=retry_sleep,
    )
    parser = WikipediaHtmlTextExtractor()
    parser.feed(html)
    extract = parser.text()
    if not extract:
        raise ValueError(f"Wikipedia HTML has an empty extract: {wikipedia_url}")

    return {
        "extract": extract,
        "title": title,
        "pageid": None,
        "revision_id": None,
        "language_host": host,
    }


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def update_characters(
    data: dict[str, Any],
    *,
    intro_only: bool,
    timeout: int,
    sleep_seconds: float,
    user_agent: str,
    retries: int,
    retry_sleep: float,
    missing_only: bool,
    batch_size: int,
    source: str,
    checkpoint_path: Path | None = None,
    save_every: int = 0,
) -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    pending: list[dict[str, Any]] = []

    for character in data["characters"]:
        if missing_only and str(character.get("description_raw") or "").strip():
            continue

        url = character.get("wikipedia_url")
        if not url:
            raise ValueError(f"Character is missing wikipedia_url: {character!r}")

        pending.append(character)

    if source in {"rest-html", "rest-summary"}:
        page_cache: dict[str, dict[str, Any]] = {}
        for fetch_index, character in enumerate(pending, start=1):
            url = str(character["wikipedia_url"])
            if url in page_cache:
                continue

            if source == "rest-html":
                try:
                    page_cache[url] = fetch_html_extract(
                        url,
                        timeout=timeout,
                        user_agent=user_agent,
                        retries=retries,
                        retry_sleep=retry_sleep,
                    )
                    page_cache[url]["source"] = "rest-html"
                except Exception:
                    page_cache[url] = fetch_summary(
                        url,
                        timeout=timeout,
                        user_agent=user_agent,
                        retries=retries,
                        retry_sleep=retry_sleep,
                    )
                    page_cache[url]["source"] = "rest-summary-fallback"
            else:
                try:
                    page_cache[url] = fetch_summary(
                        url,
                        timeout=timeout,
                        user_agent=user_agent,
                        retries=retries,
                        retry_sleep=retry_sleep,
                    )
                except HTTPError as exc:
                    if exc.code == 429:
                        raise
                    page_cache[url] = fetch_extract(
                        url,
                        intro_only=True,
                        timeout=timeout,
                        user_agent=user_agent,
                        retries=retries,
                        retry_sleep=retry_sleep,
                    )
                    page_cache[url]["source"] = "action-api-fallback"
                except Exception:
                    page_cache[url] = fetch_extract(
                        url,
                        intro_only=True,
                        timeout=timeout,
                        user_agent=user_agent,
                        retries=retries,
                        retry_sleep=retry_sleep,
                    )
                    page_cache[url]["source"] = "action-api-fallback"
                else:
                    page_cache[url]["source"] = "rest-summary"

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

            if checkpoint_path and save_every > 0 and fetch_index % save_every == 0:
                for cached_character in pending:
                    cached_page = page_cache.get(str(cached_character["wikipedia_url"]))
                    if not cached_page:
                        continue
                    cached_character["description_raw"] = cached_page["extract"]
                    cached_character["source_metadata"] = {
                        "wikipedia_title": cached_page["title"],
                        "pageid": cached_page["pageid"],
                        "revision_id": cached_page["revision_id"],
                        "language_host": cached_page["language_host"],
                        "fetched_at": fetched_at,
                        "intro_only": cached_page.get("source") != "rest-html",
                        "source": cached_page.get("source", source),
                    }
                save_yaml(checkpoint_path, data)

        for character in pending:
            page = page_cache[str(character["wikipedia_url"])]
            character["description_raw"] = page["extract"]
            character["source_metadata"] = {
                "wikipedia_title": page["title"],
                "pageid": page["pageid"],
                "revision_id": page["revision_id"],
                "language_host": page["language_host"],
                "fetched_at": fetched_at,
                "intro_only": page.get("source") != "rest-html",
                "source": page.get("source", source),
            }

        if checkpoint_path and save_every > 0:
            save_yaml(checkpoint_path, data)

        return data

    character_batches = chunked(pending, batch_size)

    for batch_index, character_batch in enumerate(character_batches, start=1):
        if source == "rest-summary":
            pages = [
                fetch_summary(
                    str(character["wikipedia_url"]),
                    timeout=timeout,
                    user_agent=user_agent,
                    retries=retries,
                    retry_sleep=retry_sleep,
                )
                for character in character_batch
            ]
        else:
            urls = [str(character["wikipedia_url"]) for character in character_batch]
            pages = fetch_extracts(
                urls,
                intro_only=intro_only,
                timeout=timeout,
                user_agent=user_agent,
                retries=retries,
                retry_sleep=retry_sleep,
            )

        for character, page in zip(character_batch, pages):
            character["description_raw"] = page["extract"]
            character["source_metadata"] = {
                "wikipedia_title": page["title"],
                "pageid": page["pageid"],
                "revision_id": page["revision_id"],
                "language_host": page["language_host"],
                "fetched_at": fetched_at,
                "intro_only": intro_only,
                "source": source,
            }

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        if checkpoint_path and save_every > 0 and batch_index % save_every == 0:
            save_yaml(checkpoint_path, data)

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
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument(
        "--source",
        choices=["action-api", "rest-summary", "rest-html"],
        default="action-api",
        help="Wikipedia endpoint to use for fetching text.",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Skip records that already have description_raw text.",
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=0,
        help="Checkpoint the output file every N batches while fetching.",
    )
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
        retries=args.retries,
        retry_sleep=args.retry_sleep,
        missing_only=args.missing_only,
        batch_size=args.batch_size,
        source=args.source,
        checkpoint_path=args.output if args.save_every > 0 else None,
        save_every=args.save_every,
    )
    save_yaml(args.output, updated)


if __name__ == "__main__":
    main()
