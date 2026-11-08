import re

_SEPARATORS = re.compile(r"[\s\-().]")
_NIGERIAN_LOCAL = re.compile(r"0([789][01]\d{8})")  # 080..., 081..., 070..., 090..., 091...
_NIGERIAN_INTL = re.compile(r"234([789][01]\d{8})")
_INTERNATIONAL = re.compile(r"\+[1-9]\d{7,14}")  # E.164: up to 15 digits


def normalise_phone(raw: str) -> str:
    """Return the number in international form (+2348012345678), or raise ValueError.

    Accepts Nigerian local (080...), Nigerian international (+234... or 234...) and any
    other international number starting with "+" (FR-33). Spaces, dashes, dots and
    brackets are ignored.
    """
    cleaned = _SEPARATORS.sub("", raw)
    if m := _NIGERIAN_LOCAL.fullmatch(cleaned):
        return f"+234{m.group(1)}"
    if m := _NIGERIAN_INTL.fullmatch(cleaned.removeprefix("+")):
        return f"+234{m.group(1)}"
    if _INTERNATIONAL.fullmatch(cleaned):
        return cleaned
    raise ValueError("Enter a valid phone number, for example 08012345678 or +2348012345678")
