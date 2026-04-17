"""Utilities for cleaning raw SEC filing HTML and extracting item sections."""

from __future__ import annotations

# Portions of this module are adapted from edgar-crawler by Lefteris Loukas
# https://github.com/lefterisloukas/edgar-crawler (GPL-3.0)
# For personal/local use only. Logic ported, not copied.

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup

REGEX_FLAGS = re.IGNORECASE | re.DOTALL | re.MULTILINE

TEN_K_ITEMS: List[str] = [
    "1",
    "1A",
    "1B",
    "1C",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "7A",
    "8",
    "9",
    "9A",
    "9B",
    "9C",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "SIGNATURE",
]

ROMAN_NUMERAL_MAP = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "5": "V",
    "6": "VI",
    "7": "VII",
    "8": "VIII",
    "9": "IX",
    "10": "X",
    "11": "XI",
    "12": "XII",
    "13": "XIII",
    "14": "XIV",
    "15": "XV",
    "16": "XVI",
    "17": "XVII",
    "18": "XVIII",
    "19": "XIX",
    "20": "XX",
}


class _HtmlStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.strict = False
        self.convert_charrefs = True
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_data(self) -> str:
        return "".join(self._chunks)

    def strip_tags(self, raw_html: str) -> str:
        self.feed(raw_html)
        return self.get_data()


@dataclass(frozen=True)
class ItemMatch:
    start: int
    end: int
    item: str


# Ported from the reference extract_items.py strip_html() behavior.
def strip_html(html_content: str) -> str:
    html_content = re.sub(r"(<\s*/\s*(div|tr|p|li)\s*>)", r"\1\n\n", html_content, flags=re.IGNORECASE)
    html_content = re.sub(r"(<\s*br\s*/?\s*>)", r"\1\n\n", html_content, flags=re.IGNORECASE)
    html_content = re.sub(r"(<\s*/\s*(th|td)\s*>)", r" \1 ", html_content, flags=re.IGNORECASE)
    return _HtmlStripper().strip_tags(html_content)


# Ported from the reference handle_spans() behavior, simplified for single-filing extraction.
def handle_spans(doc: str) -> str:
    soup = BeautifulSoup(doc, "lxml")

    for span in list(soup.find_all("span")):
        style = (span.attrs.get("style") or "").lower()
        text = span.get_text(strip=False)
        if text.strip() and not any(k in style for k in ("margin-left", "margin-right", "margin-top", "margin-bottom")):
            span.unwrap()
            continue
        if "margin-left" in style or "margin-right" in style:
            span.replace_with(" ")
        elif "margin-top" in style or "margin-bottom" in style:
            span.replace_with("\n")
        else:
            span.unwrap()

    return str(soup)


def _collapse_runs(text: str) -> str:
    text = re.sub(r"(( )*\n( )*){2,}", "#NEWLINE", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"(#NEWLINE)+", "\n", text).strip()
    text = re.sub(r"[ ]{2,}", " ", text)
    return text


# Ported from the reference clean_text() behavior and expanded for reader/diff use.
def clean_text(text: str) -> str:
    substitutions = {
        "\xa0": " ",
        "\u200b": " ",
        "\x91": "‘",
        "\x92": "’",
        "\x93": "“",
        "\x94": "”",
        "\x95": "•",
        "\x96": "-",
        "\x97": "-",
        "\x98": "˜",
        "\x99": "™",
        "\u2009": " ",
        "\u00ae": "®",
        "\u2018": "‘",
        "\u2019": "’",
        "\u201c": "“",
        "\u201d": "”",
    }
    for src, dst in substitutions.items():
        text = text.replace(src, dst)

    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", text)
    text = html.unescape(text)

    def remove_whitespace(match: re.Match[str]) -> str:
        ws = r"[^\S\r\n]"
        return f"{match[1]}{re.sub(ws, '', match[2])}{match[3]}{match[4]}"

    def remove_whitespace_signature(match: re.Match[str]) -> str:
        ws = r"[^\S\r\n]"
        return f"{match[1]}{re.sub(ws, '', match[2])}{match[4]}{match[5]}"

    text = re.sub(
        r"(\n[^\S\r\n]*)(P[^\S\r\n]*A[^\S\r\n]*R[^\S\r\n]*T)([^\S\r\n]+)((\d{1,2}|[IVX]{1,4})[AB]?)",
        remove_whitespace,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(\n[^\S\r\n]*)(I[^\S\r\n]*T[^\S\r\n]*E[^\S\r\n]*M)([^\S\r\n]+)(\d{1,2}(?:[^\S\r\n]*[ABC])?)",
        remove_whitespace,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"ITEM\s+(\d{1,2})\s+([ABC])", r"ITEM \1\2", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(\n[^\S\r\n]*)(S[^\S\r\n]*I[^\S\r\n]*G[^\S\r\n]*N[^\S\r\n]*A[^\S\r\n]*T[^\S\r\n]*U[^\S\r\n]*R[^\S\r\n]*E[^\S\r\n]*(S|\([^\S\r\n]*s[^\S\r\n]*\))?)([^\S\r\n]+)([^\S\r\n]?)",
        remove_whitespace_signature,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(ITEM|PART)(\s+\d{1,2}[AB]?)([\-•])", r"\1\2 \3 ", text, flags=re.IGNORECASE)

    text = re.sub(
        r"\n[^\S\r\n]*(TABLE\s+OF\s+CONTENTS|INDEX\s+TO\s+FINANCIAL\s+STATEMENTS|BACK\s+TO\s+CONTENTS|QUICKLINKS)[^\S\r\n]*\n",
        "\n",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(r"\n[^\S\r\n]*[-‒–—]*\d+[-‒–—]*[^\S\r\n]*\n", "\n", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\n[^\S\r\n]*\d+[^\S\r\n]*\n", "\n", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"[\n\s]F[-‒–—]*\d+", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\n[^\S\r\n]*Page\s[\d*]+[^\S\r\n]*\n", "\n", text, flags=re.IGNORECASE | re.MULTILINE)

    # Normalize line endings and paragraph spacing for diff quality.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\t+", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _collapse_runs(text)
    return text.strip()


# Ported from the reference adjust_item_patterns() behavior for 10-K section extraction.
def adjust_item_patterns(item_index: str) -> str:
    item_index_pattern = item_index

    if item_index == "9A":
        item_index_pattern = item_index_pattern.replace("A", r"[^\S\r\n]*A(?:\(T\))?")
    elif item_index == "SIGNATURE":
        return r"SIGNATURE(?:s|\(s\))?"
    elif "A" in item_index:
        item_index_pattern = item_index_pattern.replace("A", r"[^\S\r\n]*A")
    elif "B" in item_index:
        item_index_pattern = item_index_pattern.replace("B", r"[^\S\r\n]*B")
    elif "C" in item_index:
        item_index_pattern = item_index_pattern.replace("C", r"[^\S\r\n]*C")

    if "." in item_index_pattern:
        item_index_pattern = item_index_pattern.replace(".", r"\.")

    if item_index in ROMAN_NUMERAL_MAP:
        item_index_pattern = f"(?:{ROMAN_NUMERAL_MAP[item_index]}|{item_index})"

    return rf"ITEMS?\s*{item_index_pattern}"


def _item_header_regex(item_index: str) -> re.Pattern[str]:
    pattern = adjust_item_patterns(item_index)
    return re.compile(rf"(^|\n)[^\S\r\n]*{pattern}[.*~\-:\s\(]", flags=re.IGNORECASE | re.MULTILINE)


def _find_item_headers(text: str, items: Sequence[str]) -> List[ItemMatch]:
    matches: List[ItemMatch] = []
    for item in items:
        regex = _item_header_regex(item)
        for match in regex.finditer(text):
            start = match.start()
            end = match.end()
            matches.append(ItemMatch(start=start, end=end, item=item))
    matches.sort(key=lambda m: (m.start, len(m.item)))
    return matches


def _prefer_body_matches(matches: Sequence[ItemMatch], text: str) -> List[ItemMatch]:
    filtered: List[ItemMatch] = []
    for m in matches:
        window = text[m.start : min(len(text), m.start + 300)]
        if re.search(r"table of contents|index", window, flags=re.IGNORECASE):
            continue
        filtered.append(m)
    return filtered or list(matches)


# Simplified port of parse_item() for on-demand single-filing extraction.
def parse_item(text: str, item_index: str, next_item_list: Sequence[str], positions: Optional[List[int]] = None) -> Tuple[str, List[int]]:
    positions = list(positions or [])
    current_re = _item_header_regex(item_index)
    current_matches = list(current_re.finditer(text))
    if not current_matches:
        return "", positions

    start_match = None
    min_allowed = positions[-1] if positions else 0
    for match in current_matches:
        if match.start() >= min_allowed:
            start_match = match
            break
    if start_match is None:
        start_match = current_matches[-1]

    start = start_match.start()
    end: Optional[int] = None

    for next_item in next_item_list:
        next_re = _item_header_regex(next_item)
        candidate_matches = [m for m in next_re.finditer(text, pos=start_match.end()) if m.start() > start]
        if candidate_matches:
            end = candidate_matches[0].start()
            break

    if end is None:
        end = len(text)

    positions.append(end)
    return text[start:end].strip(), positions


def _normalize_section(section: str) -> str:
    value = section.upper().replace("ITEM", "").replace(" ", "")
    return value


def extract_section(raw_html: str, section: str = "1A") -> str:
    normalized = _normalize_section(section)
    if normalized not in TEN_K_ITEMS:
        raise ValueError(f"Unsupported section: {section}")

    span_fixed = handle_spans(raw_html)
    soup = BeautifulSoup(span_fixed, "lxml")

    for tag in soup(["script", "style", "ix:header", "header", "footer", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(lambda t: t.name and t.name.lower().startswith("ix:")):
        tag.unwrap()

    stripped = strip_html(str(soup))
    cleaned = clean_text(stripped)
    headers = _prefer_body_matches(_find_item_headers(cleaned, TEN_K_ITEMS), cleaned)
    ordered_items = [m.item for m in headers]

    if normalized not in ordered_items:
        # Fallback: parse directly against the canonical ordering.
        idx = TEN_K_ITEMS.index(normalized)
        extracted, _ = parse_item(cleaned, normalized, TEN_K_ITEMS[idx + 1 :], [])
        return extracted.strip()

    idx = ordered_items.index(normalized)
    next_items = ordered_items[idx + 1 :]
    extracted, _ = parse_item(cleaned, normalized, next_items, [])
    return extracted.strip()


__all__ = [
    "strip_html",
    "handle_spans",
    "clean_text",
    "adjust_item_patterns",
    "parse_item",
    "extract_section",
]
