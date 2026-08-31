"""
Tidy the figures in a summary before they reach the page.

A model reading "Rs 2,099.99 crore" out of a PDF sometimes writes it back as
"Rs 20,99.99 crore". The digits survive; the comma lands in the wrong place.
That is not a small thing on a filings dashboard - it turns a Rs 2,099 crore
capital raise into what looks like Rs 20 crore, and a reader has no way to
tell which one the document actually said.

So every figure is checked against the two grouping conventions that are
actually used - Indian (12,34,567) and Western (1,234,567). Anything matching
either is left exactly as written. Only a grouping that is neither, and so
cannot have come from the document, is rebuilt from its own digits using
Indian grouping. The digits themselves are never altered.
"""

import re

# A number with at least one comma in it, plus optional decimals. Groups of
# one digit are allowed so that a mangled figure is matched whole - otherwise
# "1,23,4" matches only its first half and the repair leaves a stray ",4".
_GROUPED = re.compile(r"\d{1,3}(?:,\d{1,3})+(?:\.\d+)?")


def _indian(digits):
    """1234567 -> 12,34,567. The last three, then twos."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def _valid(groups):
    """Is this how either convention would have written it?"""
    if len(groups) < 2:
        return True
    first, rest = groups[0], groups[1:]
    western = all(len(g) == 3 for g in rest) and 1 <= len(first) <= 3
    indian = (len(rest[-1]) == 3
              and all(len(g) == 2 for g in rest[:-1])
              and 1 <= len(first) <= 2)
    return western or indian


def fix(text):
    """Repair any misgrouped figure in a piece of text. Digits are preserved."""
    if not text:
        return text

    def repair(m):
        whole = m.group(0)
        intpart, _, dec = whole.partition(".")
        digits = intpart.replace(",", "")
        # Fewer than four digits cannot be a grouped number, so a comma there
        # is a decimal comma or a list - "5,4 million", "shares 1,2". Leave it.
        if len(digits) < 4 or _valid(intpart.split(",")):
            return whole
        fixed = _indian(digits)
        return f"{fixed}.{dec}" if dec else fixed

    # One rupee sign, so a column of figures reads consistently.
    return _GROUPED.sub(repair, text.replace("₹", "Rs "))\
                   .replace("Rs  ", "Rs ").replace("‑", "-")


def fix_all(record):
    """Tidy every field of a summary that carries figures. Mutates and returns."""
    for field in ("summary", "why_it_matters", "headline"):
        if record.get(field):
            record[field] = fix(record[field])
    nums = record.get("key_numbers")
    if isinstance(nums, list):
        record["key_numbers"] = [fix(str(n)) for n in nums]
    return record
