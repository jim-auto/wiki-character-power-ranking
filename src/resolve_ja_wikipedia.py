"""Resolve character Wikipedia URLs to Japanese Wikipedia URLs via Wikidata."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import yaml

from fetch_wikipedia import parse_wikipedia_url


DEFAULT_INPUT = Path("data/seed_characters.yaml")
DEFAULT_OUTPUT = Path("data/seed_characters.yaml")
DEFAULT_REPORT = Path("data/ja_wikipedia_resolution_report.yaml")
DEFAULT_USER_AGENT = (
    "wiki-character-power-index/0.1 "
    "(educational prototype; resolves Japanese Wikipedia sources)"
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
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False, width=1000)


def request_json(url: str, *, timeout: int, user_agent: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def build_api_url(host: str, params: dict[str, str | int]) -> str:
    return f"https://{host}/w/api.php?{urlencode(params, quote_via=quote)}"


def build_aliases(payload: dict[str, Any]) -> dict[str, str]:
    query = payload.get("query", {})
    aliases: dict[str, str] = {}
    for item in query.get("normalized", []) or []:
        aliases[str(item.get("from"))] = str(item.get("to"))
    for item in query.get("redirects", []) or []:
        aliases[str(item.get("from"))] = str(item.get("to"))
    return {key: value for key, value in aliases.items() if key and value}


def resolve_alias(title: str, aliases: dict[str, str]) -> str:
    current = title
    for _ in range(4):
        next_title = aliases.get(current)
        if not next_title or next_title == current:
            return current
        current = next_title
    return current


def fetch_wikibase_ids(
    url_title_pairs: list[tuple[str, str, str]],
    *,
    timeout: int,
    user_agent: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    by_host: dict[str, list[tuple[str, str]]] = {}
    for url, host, title in url_title_pairs:
        by_host.setdefault(host, []).append((url, title))

    for host, pairs in by_host.items():
        for batch in chunked(pairs, 50):
            titles = [title for _url, title in batch]
            payload = request_json(
                build_api_url(
                    host,
                    {
                        "action": "query",
                        "format": "json",
                        "prop": "pageprops",
                        "ppprop": "wikibase_item",
                        "redirects": 1,
                        "titles": "|".join(titles),
                    },
                ),
                timeout=timeout,
                user_agent=user_agent,
            )
            aliases = build_aliases(payload)
            pages = payload.get("query", {}).get("pages", {})
            pages_by_title = {str(page.get("title")): page for page in pages.values()}

            for url, title in batch:
                resolved_title = resolve_alias(title, aliases)
                page = pages_by_title.get(resolved_title) or pages_by_title.get(title)
                qid = ((page or {}).get("pageprops") or {}).get("wikibase_item")
                if qid:
                    result[url] = str(qid)

            time.sleep(0.1)

    return result


def fetch_ja_sitelinks(
    qids: list[str],
    *,
    timeout: int,
    user_agent: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for batch in chunked(qids, 50):
        payload = request_json(
            "https://www.wikidata.org/w/api.php?"
            + urlencode(
                {
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(batch),
                    "props": "sitelinks/urls",
                    "sitefilter": "jawiki",
                },
                quote_via=quote,
            ),
            timeout=timeout,
            user_agent=user_agent,
        )
        entities = payload.get("entities", {})
        for qid, entity in entities.items():
            sitelink = (entity.get("sitelinks") or {}).get("jawiki") or {}
            url = sitelink.get("url")
            if url:
                result[str(qid)] = str(url)
        time.sleep(0.1)
    return result


def search_ja_wikipedia(
    query: str,
    *,
    timeout: int,
    user_agent: str,
) -> str | None:
    payload = request_json(
        build_api_url(
            "ja.wikipedia.org",
            {
                "action": "query",
                "format": "json",
                "list": "search",
                "srlimit": 1,
                "srsearch": query,
            },
        ),
        timeout=timeout,
        user_agent=user_agent,
    )
    results = payload.get("query", {}).get("search", [])
    if not results:
        return None
    title = str(results[0].get("title") or "").strip()
    if not title:
        return None
    return f"https://ja.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"


def resolve_data(
    data: dict[str, Any],
    *,
    timeout: int,
    user_agent: str,
    search_fallback: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    url_title_pairs: list[tuple[str, str, str]] = []
    for character in data["characters"]:
        url = str(character.get("wikipedia_url") or "")
        host, title = parse_wikipedia_url(url)
        if host == "ja.wikipedia.org":
            continue
        url_title_pairs.append((url, host, title))

    qids_by_url = fetch_wikibase_ids(url_title_pairs, timeout=timeout, user_agent=user_agent)
    ja_urls_by_qid = fetch_ja_sitelinks(
        sorted(set(qids_by_url.values())),
        timeout=timeout,
        user_agent=user_agent,
    )

    resolved = []
    fallback_resolved = []
    unresolved = []
    already_ja = []

    for character in data["characters"]:
        original_url = str(character.get("wikipedia_url") or "")
        host, _title = parse_wikipedia_url(original_url)
        if host == "ja.wikipedia.org":
            already_ja.append({"name": character.get("name"), "wikipedia_url": original_url})
            continue

        qid = qids_by_url.get(original_url)
        ja_url = ja_urls_by_qid.get(str(qid))
        if ja_url:
            character["source_wikipedia_url_original"] = original_url
            character["wikipedia_url"] = ja_url
            resolved.append(
                {
                    "name": character.get("name"),
                    "original_url": original_url,
                    "wikidata_id": qid,
                    "ja_url": ja_url,
                }
            )
        elif search_fallback:
            fallback_url = search_ja_wikipedia(
                str(character.get("name") or ""),
                timeout=timeout,
                user_agent=user_agent,
            )
            if fallback_url:
                character["source_wikipedia_url_original"] = original_url
                character["source_resolution"] = "jawiki_search_fallback"
                character["wikipedia_url"] = fallback_url
                fallback_resolved.append(
                    {
                        "name": character.get("name"),
                        "original_url": original_url,
                        "wikidata_id": qid,
                        "ja_url": fallback_url,
                    }
                )
            else:
                unresolved.append(
                    {
                        "name": character.get("name"),
                        "original_url": original_url,
                        "wikidata_id": qid,
                    }
                )
        else:
            unresolved.append(
                {
                    "name": character.get("name"),
                    "original_url": original_url,
                    "wikidata_id": qid,
                }
            )

    report = {
        "total": len(data["characters"]),
        "already_ja": len(already_ja),
        "resolved": len(resolved),
        "fallback_resolved": len(fallback_resolved),
        "unresolved": len(unresolved),
        "fallback_resolved_items": fallback_resolved,
        "unresolved_items": unresolved,
    }
    return data, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve character URLs to Japanese Wikipedia.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument(
        "--search-fallback",
        action="store_true",
        help="Use the first Japanese Wikipedia search result when no jawiki sitelink exists.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    updated, report = resolve_data(
        data,
        timeout=args.timeout,
        user_agent=args.user_agent,
        search_fallback=args.search_fallback,
    )
    save_yaml(args.output, updated)
    save_yaml(args.report, report)
    print(
        f"total={report['total']} resolved={report['resolved']} "
        f"fallback={report['fallback_resolved']} already_ja={report['already_ja']} "
        f"unresolved={report['unresolved']}"
    )


if __name__ == "__main__":
    main()
