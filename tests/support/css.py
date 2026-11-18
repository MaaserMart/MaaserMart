"""Read the stylesheet the way a browser resolves it, as far as text can.

The contract tests used to assert that a declaration *appears* in `site.css`
(audit T2). That passes when a later block overrides the same property, when the
selector was swallowed into a list, or when no element on the page ever carries
the class. This helper answers the two questions a regex cannot: what is the
final value of a property for one selector, and is that selector actually used
by the page being tested.
"""

from __future__ import annotations

import re

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def _without_at_rules(text: str) -> str:
    """Drop every `@media`/`@supports`/`@import` block, condition and all.

    A desktop rule and its mobile override declare the same property; merging
    both without evaluating the condition would answer with the mobile value.
    These tests assert the unconditional rule, so conditions are removed rather
    than guessed at.
    """
    out = []
    index = 0
    while True:
        at = text.find("@", index)
        if at == -1:
            out.append(text[index:])
            return "".join(out)
        brace = text.find("{", at)
        semicolon = text.find(";", at)
        if brace == -1 or (semicolon != -1 and semicolon < brace):
            # A statement at-rule (`@import ...;`) ends at the semicolon.
            out.append(text[index:at])
            index = semicolon + 1 if semicolon != -1 else len(text)
            continue
        depth = 0
        end = brace
        while end < len(text):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        out.append(text[index:at])
        index = end + 1


def _blocks(css: str):
    """Yield (selectors, declarations) in source order, unconditional rules only."""
    text = _without_at_rules(_COMMENT.sub("", css))
    for match in _BLOCK.finditer(text):
        selectors = [part.strip() for part in match.group(1).split(",")]
        yield selectors, match.group(2)


def declarations(css: str, selector: str) -> dict[str, str]:
    """The declarations that end up applying to one selector.

    Every block mentioning the selector is merged in source order, later blocks
    winning, which is how a browser resolves same-specificity rules. Media
    queries are not evaluated; callers should assert rules that only one block
    declares.
    """
    result: dict[str, str] = {}
    for selectors, body in _blocks(css):
        if selector not in selectors:
            continue
        for line in body.split(";"):
            if ":" not in line:
                continue
            prop, value = line.split(":", 1)
            result[prop.strip()] = value.strip()
    return result


def value(css: str, selector: str, prop: str) -> str | None:
    """The final value of one property for one selector, or None if unset."""
    return declarations(css, selector).get(prop)
