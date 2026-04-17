"""Paragraph-aware filing diff utilities."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Dict, List


def split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def diff_sections(current_text: str, prior_text: str) -> Dict[str, List[dict]]:
    current = split_paragraphs(current_text)
    prior = split_paragraphs(prior_text)
    matcher = SequenceMatcher(a=prior, b=current, autojunk=False)

    added: List[dict] = []
    removed: List[dict] = []
    modified: List[dict] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            for idx, paragraph in enumerate(current[j1:j2], start=j1):
                added.append({"text": paragraph, "paragraph_index": idx})
        elif tag == "delete":
            for idx, paragraph in enumerate(prior[i1:i2], start=i1):
                removed.append({"text": paragraph, "paragraph_index": idx})
        elif tag == "replace":
            left = prior[i1:i2]
            right = current[j1:j2]
            count = max(len(left), len(right))
            for offset in range(count):
                old_text = left[offset] if offset < len(left) else ""
                new_text = right[offset] if offset < len(right) else ""
                modified.append(
                    {
                        "prior_text": old_text,
                        "current_text": new_text,
                        "prior_paragraph_index": i1 + offset if offset < len(left) else None,
                        "current_paragraph_index": j1 + offset if offset < len(right) else None,
                    }
                )
    return {"added": added, "removed": removed, "modified": modified}
