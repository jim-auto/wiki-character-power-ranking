"""Extract character-specific text from shared Japanese Wikipedia pages.

Some records can only be linked to a Japanese Wikipedia list, work, or
universe page. This script fetches those shared pages as REST HTML, finds a
heading or character-like line near the target name, and replaces only that
record's raw description when a conservative match is found.
"""

from __future__ import annotations

import argparse
import re
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import yaml

from fetch_wikipedia import (
    DEFAULT_USER_AGENT,
    build_html_url,
    parse_wikipedia_url,
    request_text,
)


DEFAULT_INPUT = Path("data/characters.yaml")
DEFAULT_REPORT = Path("data/section_extraction_report.yaml")
DEFAULT_TARGET_RESOLUTIONS = {
    "universe_fallback",
    "manual_jawiki_fallback",
    "jawiki_search_fallback",
}

BODY_TAGS = {"p", "li", "dd"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "dt"}
HEADING_RANKS = {
    "h1": 1,
    "h2": 2,
    "h3": 3,
    "h4": 4,
    "h5": 5,
    "h6": 6,
    "dt": 7,
}
SKIP_TAGS = {
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
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

CHARACTER_CONTEXT_TERMS = [
    "登場人物",
    "人物",
    "主人公",
    "キャラクター",
    "ヒーロー",
    "ヴィラン",
    "敵",
    "味方",
    "役",
    "声",
    "演",
    "能力",
    "戦闘",
    "忍",
    "魔法",
    "巨人",
    "隊",
    "組織",
]
BODY_CHARACTER_CONTEXT_TERMS = [
    "登場する架空の人物",
    "登場する架空",
    "本作の主人公",
    "物語の主人公",
    "キャラクター",
]
REFERENCE_ONLY_TERMS = [
    "詳しくは",
    "詳細は",
    "項を参照",
    "を参照",
]


@dataclass(frozen=True)
class TextLine:
    text: str
    kind: str
    tag: str


@dataclass(frozen=True)
class Alias:
    value: str
    normalized: str
    source: str


@dataclass(frozen=True)
class Match:
    line_index: int
    alias: Alias
    score: int
    kind: str


class WikipediaSectionParser(HTMLParser):
    """Convert REST HTML to typed text lines while preserving headings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[TextLine] = []
        self.skip_depth = 0
        self.current_tag: str | None = None
        self.current_kind: str | None = None
        self.current_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            if tag not in VOID_TAGS:
                self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return
        if tag in HEADING_TAGS:
            self._start_block(tag, "heading")
        elif tag in BODY_TAGS:
            self._start_block(tag, "body")
        elif tag == "br":
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if self.skip_depth > 0:
            return
        if tag == self.current_tag or tag in HEADING_TAGS or tag in BODY_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0 or self.current_kind is None:
            return
        text = " ".join(data.split())
        if text:
            self.current_parts.append(text)

    def _start_block(self, tag: str, kind: str) -> None:
        self._flush()
        self.current_tag = tag
        self.current_kind = kind
        self.current_parts = []

    def _flush(self) -> None:
        if self.current_kind is None:
            return
        text = " ".join(" ".join(self.current_parts).split()).strip()
        if text:
            self.lines.append(TextLine(text=text, kind=self.current_kind, tag=self.current_tag or ""))
        self.current_tag = None
        self.current_kind = None
        self.current_parts = []

    def close(self) -> None:
        super().close()
        self._flush()


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


def url_fragment(url: str) -> str:
    fragment = unquote(urlsplit(url).fragment).replace("_", " ").strip()
    return fragment


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s\-_・･・「」『』（）()［］\[\]【】<>〈〉、。，．・:：/／]", "", normalized)


def strip_parenthetical(value: str) -> str:
    return re.sub(r"[（(].*?[）)]", "", value).strip()


def add_alias(
    aliases: list[Alias],
    seen: set[str],
    value: Any,
    source: str,
    *,
    excluded_normalized: set[str] | None = None,
) -> None:
    if not isinstance(value, str):
        return
    value = " ".join(value.split()).strip()
    if not value:
        return
    normalized = normalize_text(value)
    if len(normalized) < 1 or normalized in seen:
        return
    if excluded_normalized and normalized in excluded_normalized:
        return
    seen.add(normalized)
    aliases.append(Alias(value=value, normalized=normalized, source=source))


def build_aliases(character: dict[str, Any]) -> list[Alias]:
    aliases: list[Alias] = []
    seen: set[str] = set()
    character_name_normalized = normalize_text(str(character.get("name") or ""))
    excluded_normalized: set[str] = set()

    try:
        _host, page_title = parse_wikipedia_url(str(character.get("wikipedia_url") or ""))
        page_title_normalized = normalize_text(page_title)
        if page_title_normalized != character_name_normalized:
            excluded_normalized.add(page_title_normalized)
            stripped_page_title = normalize_text(strip_parenthetical(page_title))
            if stripped_page_title != character_name_normalized:
                excluded_normalized.add(stripped_page_title)
    except ValueError:
        pass

    add_alias(aliases, seen, character.get("name"), "name")
    add_alias(
        aliases,
        seen,
        character.get("source_name_original"),
        "source_name_original",
        excluded_normalized=excluded_normalized,
    )
    add_alias(
        aliases,
        seen,
        character.get("source_wikidata_label_ja"),
        "source_wikidata_label_ja",
        excluded_normalized=excluded_normalized,
    )

    for key in ("name", "source_name_original", "source_wikidata_label_ja"):
        stripped = strip_parenthetical(str(character.get(key) or ""))
        add_alias(
            aliases,
            seen,
            stripped,
            f"{key}_without_parentheses",
            excluded_normalized=excluded_normalized,
        )

    fragment = url_fragment(str(character.get("wikipedia_url") or ""))
    add_alias(aliases, seen, fragment, "url_fragment", excluded_normalized=excluded_normalized)
    add_alias(
        aliases,
        seen,
        strip_parenthetical(fragment),
        "url_fragment_without_parentheses",
        excluded_normalized=excluded_normalized,
    )

    return aliases


def has_character_context(text: str) -> bool:
    return any(term in text for term in CHARACTER_CONTEXT_TERMS)


def has_body_character_context(text: str) -> bool:
    return any(term in text for term in BODY_CHARACTER_CONTEXT_TERMS)


def compact_display_text(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).strip())


def heading_matches_alias(line: TextLine, alias: Alias) -> bool:
    normalized = normalize_text(line.text)
    if normalized == alias.normalized:
        return True

    compact_line = compact_display_text(line.text)
    compact_alias = compact_display_text(alias.value)
    if not compact_alias or not compact_line.startswith(compact_alias):
        return False

    remaining = compact_line[len(compact_alias) :]
    return bool(remaining) and remaining[0] in {"（", "(", "/", "／"}


def line_starts_with_alias(line: TextLine, alias: Alias) -> bool:
    compact_line = compact_display_text(line.text)
    compact_alias = compact_display_text(alias.value)
    if not compact_alias or not compact_line.startswith(compact_alias):
        return False
    remaining = compact_line[len(compact_alias) :]
    return not remaining or remaining[0] in {"（", "(", "/", "／", "は"}


def line_matches_alias(line: TextLine, alias: Alias) -> bool:
    normalized = normalize_text(line.text)
    if not alias.normalized:
        return False
    if line.kind == "heading":
        return heading_matches_alias(line, alias)
    if len(alias.normalized) <= 2:
        return False
    return alias.normalized in normalized


def score_match(line: TextLine, alias: Alias) -> int:
    normalized = normalize_text(line.text)
    score = 0
    if line.kind == "heading":
        score += 80
        if normalized == alias.normalized:
            score += 40
        elif heading_matches_alias(line, alias):
            score += 25
    elif line_starts_with_alias(line, alias) and has_body_character_context(line.text):
        score += 55
    else:
        score += 10

    if alias.source in {"name", "source_wikidata_label_ja", "source_name_original"}:
        score += 10
    if len(alias.normalized) <= 2:
        score -= 30
    return score


def heading_rank(line: TextLine) -> int:
    return HEADING_RANKS.get(line.tag, 99)


def find_section_boundary(lines: list[TextLine], start: int) -> int:
    if lines[start].kind != "heading":
        return find_next_heading(lines, start)

    start_rank = heading_rank(lines[start])
    for candidate in range(start + 1, len(lines)):
        if lines[candidate].kind == "heading" and heading_rank(lines[candidate]) <= start_rank:
            return candidate
    return len(lines)


def section_preview_for_match(lines: list[TextLine], index: int) -> str:
    end = find_section_boundary(lines, index)
    return "\n".join(line.text for line in lines[index:end]).strip()


def is_reference_only_section(text: str) -> bool:
    if len(text) > 160:
        return False
    return any(term in text for term in REFERENCE_ONLY_TERMS)


def contextual_match_score(lines: list[TextLine], match: Match) -> int:
    section_text = section_preview_for_match(lines, match.line_index)
    score = match.score + min(len(section_text) // 80, 35)
    if is_reference_only_section(section_text):
        score -= 55
    if len(section_text) <= len(match.alias.value) + 8:
        score -= 25
    return score


def find_best_match(lines: list[TextLine], aliases: list[Alias]) -> Match | None:
    best: Match | None = None
    for index, line in enumerate(lines):
        for alias in aliases:
            if not line_matches_alias(line, alias):
                continue
            if line.kind != "heading" and (
                not line_starts_with_alias(line, alias) or not has_body_character_context(line.text)
            ):
                continue
            score = score_match(line, alias)
            if line.kind != "heading" and score < 35:
                continue
            match = Match(line_index=index, alias=alias, score=score, kind=line.kind)
            match = Match(
                line_index=index,
                alias=alias,
                score=contextual_match_score(lines, match),
                kind=line.kind,
            )
            if best is None or match.score > best.score:
                best = match
    return best


def find_previous_heading(lines: list[TextLine], index: int, max_distance: int = 3) -> int | None:
    for candidate in range(index - 1, max(-1, index - max_distance - 1), -1):
        if lines[candidate].kind == "heading":
            return candidate
    return None


def find_next_heading(lines: list[TextLine], index: int) -> int:
    for candidate in range(index + 1, len(lines)):
        if lines[candidate].kind == "heading":
            return candidate
    return len(lines)


def compact_section(lines: Iterable[TextLine], *, max_chars: int) -> str:
    parts: list[str] = []
    current_length = 0
    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        next_length = current_length + len(text) + (1 if parts else 0)
        if parts and next_length > max_chars:
            break
        parts.append(text)
        current_length = next_length
    return "\n".join(parts).strip()


def extract_section(
    lines: list[TextLine],
    character: dict[str, Any],
    *,
    max_lines: int,
    max_chars: int,
) -> dict[str, Any] | None:
    aliases = build_aliases(character)
    if not aliases:
        return None

    match = find_best_match(lines, aliases)
    if match is None:
        return None

    start = match.line_index
    if lines[match.line_index].kind != "heading":
        previous_heading = find_previous_heading(lines, match.line_index)
        if previous_heading is not None and line_matches_alias(lines[previous_heading], match.alias):
            start = previous_heading
        elif line_starts_with_alias(lines[match.line_index], match.alias):
            start = match.line_index
        else:
            start = max(0, match.line_index - 1)

    end = find_section_boundary(lines, start)
    end = min(end, start + max_lines)
    section = compact_section(lines[start:end], max_chars=max_chars)
    if not section:
        return None

    return {
        "section": section,
        "matched_alias": match.alias.value,
        "alias_source": match.alias.source,
        "match_kind": match.kind,
        "match_score": match.score,
        "line_index": match.line_index,
    }


def fetch_page_lines(
    wikipedia_url: str,
    *,
    timeout: int,
    user_agent: str,
    retries: int,
    retry_sleep: float,
) -> tuple[list[TextLine], dict[str, Any]]:
    host, title = parse_wikipedia_url(wikipedia_url)
    html_source = "rest-html"
    try:
        html = request_text(
            build_html_url(host, title),
            timeout=timeout,
            user_agent=user_agent,
            retries=retries,
            retry_sleep=retry_sleep,
        )
    except Exception:
        html_source = "page-html-fallback"
        slug = quote(title.replace(" ", "_"), safe="")
        html = request_text(
            f"https://{host}/wiki/{slug}",
            timeout=timeout,
            user_agent=user_agent,
            retries=retries,
            retry_sleep=retry_sleep,
        )
    parser = WikipediaSectionParser()
    parser.feed(html)
    parser.close()
    return parser.lines, {
        "wikipedia_title": title,
        "language_host": host,
        "section_html_source": html_source,
    }


def target_characters(
    characters: list[dict[str, Any]],
    *,
    target_resolutions: set[str],
    include_shared: bool,
) -> list[dict[str, Any]]:
    base_counts = Counter(base_wikipedia_url(str(character.get("wikipedia_url") or "")) for character in characters)
    targets: list[dict[str, Any]] = []

    for character in characters:
        url = str(character.get("wikipedia_url") or "")
        resolution = character.get("source_resolution")
        shared_source = include_shared and base_counts[base_wikipedia_url(url)] > 1
        has_fragment = bool(url_fragment(url))
        if resolution in target_resolutions or shared_source or has_fragment:
            targets.append(character)

    return targets


def grouped_by_base_url(characters: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for character in characters:
        groups[base_wikipedia_url(str(character.get("wikipedia_url") or ""))].append(character)
    return dict(groups)


def apply_sections(
    data: dict[str, Any],
    *,
    target_resolutions: set[str],
    include_shared: bool,
    timeout: int,
    sleep_seconds: float,
    user_agent: str,
    retries: int,
    retry_sleep: float,
    max_pages: int | None,
    max_failures: int | None,
    max_lines: int,
    max_chars: int,
    dry_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    characters = data["characters"]
    targets = target_characters(
        characters,
        target_resolutions=target_resolutions,
        include_shared=include_shared,
    )
    groups = grouped_by_base_url(targets)
    fetched_at = datetime.now(timezone.utc).isoformat()
    report_items: list[dict[str, Any]] = []
    failed_pages: list[dict[str, str]] = []
    pages_fetched = 0
    processed_pages = 0
    updated = 0
    unchanged_no_match = 0

    for page_index, (base_url, page_characters) in enumerate(groups.items(), start=1):
        if max_pages is not None and page_index > max_pages:
            break
        processed_pages += 1

        try:
            lines, page_metadata = fetch_page_lines(
                base_url,
                timeout=timeout,
                user_agent=user_agent,
                retries=retries,
                retry_sleep=retry_sleep,
            )
            pages_fetched += 1
        except Exception as exc:
            failed_pages.append({"url": base_url, "error": str(exc)})
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            if max_failures is not None and len(failed_pages) >= max_failures:
                break
            continue

        for character in page_characters:
            result = extract_section(
                lines,
                character,
                max_lines=max_lines,
                max_chars=max_chars,
            )
            if result is None:
                unchanged_no_match += 1
                report_items.append(
                    {
                        "name": character.get("name"),
                        "url": character.get("wikipedia_url"),
                        "status": "unchanged_no_match",
                    }
                )
                continue

            updated += 1
            report_items.append(
                {
                    "name": character.get("name"),
                    "url": character.get("wikipedia_url"),
                    "status": "updated" if not dry_run else "dry_run_updated",
                    "matched_alias": result["matched_alias"],
                    "alias_source": result["alias_source"],
                    "match_kind": result["match_kind"],
                    "match_score": result["match_score"],
                    "chars": len(result["section"]),
                    "excerpt": str(result["section"])[:180],
                }
            )

            if dry_run:
                continue

            character["description_raw"] = result["section"]
            metadata = dict(character.get("source_metadata") or {})
            metadata.update(page_metadata)
            metadata["source"] = "rest-html-section"
            metadata["section_extracted_at"] = fetched_at
            metadata["section_source_url"] = base_url
            metadata["section_matched_alias"] = result["matched_alias"]
            metadata["section_alias_source"] = result["alias_source"]
            metadata["section_match_kind"] = result["match_kind"]
            metadata["section_match_score"] = result["match_score"]
            metadata["section_line_index"] = result["line_index"]
            character["source_metadata"] = metadata

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    report = {
        "generated_at": fetched_at,
        "dry_run": dry_run,
        "total_characters": len(characters),
        "target_characters": len(targets),
        "target_pages": len(groups),
        "processed_pages": processed_pages,
        "pages_fetched": pages_fetched,
        "updated": updated,
        "unchanged_no_match": unchanged_no_match,
        "failed_pages": failed_pages,
        "items": report_items,
    }
    return data, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract character-specific sections from shared Japanese Wikipedia pages."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--source-resolution",
        action="append",
        dest="source_resolutions",
        default=None,
        help="Source-resolution value to target. Can be repeated.",
    )
    parser.add_argument("--no-shared", action="store_true", help="Do not target records sharing a base URL.")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=1.5)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-sleep", type=float, default=5.0)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--max-failures", type=int, default=10)
    parser.add_argument("--max-lines", type=int, default=14)
    parser.add_argument("--max-chars", type=int, default=2400)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = load_yaml(args.input)
    target_resolutions = set(args.source_resolutions or DEFAULT_TARGET_RESOLUTIONS)
    updated_data, report = apply_sections(
        data,
        target_resolutions=target_resolutions,
        include_shared=not args.no_shared,
        timeout=args.timeout,
        sleep_seconds=args.sleep,
        user_agent=args.user_agent,
        retries=args.retries,
        retry_sleep=args.retry_sleep,
        max_pages=args.max_pages,
        max_failures=args.max_failures,
        max_lines=args.max_lines,
        max_chars=args.max_chars,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        save_yaml(args.output, updated_data)
    save_yaml(args.report, report)


if __name__ == "__main__":
    main()
