"""FFH R114 experimental protected-text gate. No I/O, no automatic approvals.

Callers supply a translation function for one chosen language. Protect only exact
{{TOKEN_NAME}} placeholders by never passing them to the translation model.
Number/unit changes remain HOLD requiring qualified human review.
This module has NOT been enabled in the FFH API or production.
"""
from __future__ import annotations
import re
import unicodedata

TOKEN = re.compile(r"(\{\{[A-Z][A-Z0-9_]*\}\})")
NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")
UNITS = re.compile(r"(?:\b(?:kg|mg|g|mL|L)\b|°C|°F|%)")


def normalize_number(token):
    out = []
    for ch in token:
        if ch.isdigit():
            try:
                out.append(str(unicodedata.decimal(ch)))
            except (ValueError, TypeError):
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def content_numbers(text):
    return sorted(normalize_number(x) for x in NUMBER.findall(text))


def hold(*reasons):
    return {"status": "held", "reasons": list(reasons), "draft": None,
            "human_approved": False, "production_writes": 0}


def guarded_candidate(source, translate_fn, max_chars=4096, max_tokens=20):
    if not isinstance(source, str) or not source.strip():
        return hold("empty_source")
    if len(source) > max_chars:
        return hold("source_too_long")
    markers = TOKEN.findall(source)
    if len(markers) > max_tokens:
        return hold("too_many_placeholders")
    stripped = TOKEN.sub("", source)
    if "{{" in stripped or "}}" in stripped:
        return hold("malformed_placeholder")
    if not callable(translate_fn):
        return hold("missing_translator")

    pieces = TOKEN.split(source)
    segments = []
    for piece in pieces:
        if not piece:
            continue
        if TOKEN.fullmatch(piece):
            segments.append(piece)
        elif not piece.strip():
            segments.append(piece)
        else:
            try:
                result = translate_fn(piece)
            except Exception:
                return hold("translator_exception")
            if not isinstance(result, str) or not result.strip():
                return hold("empty_translation_segment")
            segments.append(result)
    draft = "".join(segments)
    problems = []
    if TOKEN.findall(draft) != markers:
        problems.append("placeholder_integrity")
    if content_numbers(source) != content_numbers(draft):
        problems.append("numeric_integrity")
    if sorted(UNITS.findall(source)) != sorted(UNITS.findall(draft)):
        problems.append("unit_integrity")
    if not draft.strip():
        problems.append("empty_result")
    # Even a clean result remains unreviewed, never automatically approved.
    return {
        "status": "held" if problems else "provisional_candidate",
        "reasons": problems,
        "draft": draft if not problems else None,
        "human_approved": False,
        "production_writes": 0,
        "protected_placeholders": len(markers),
    }
