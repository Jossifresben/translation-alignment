"""Render alignment JSON into HTML fragments for the viewer.

Kept pure-Python (no Jinja) so it can be unit-tested without a Flask app context.
The route layer invokes these helpers and passes the resulting HTML as safe markup
to Jinja.
"""
from __future__ import annotations

from html import escape


def token_variant_map(alignment: dict, tradition_id: str) -> dict[int, str]:
    """Map token index → variant for the given tradition.

    Tokens not covered by any group default to 'aligned'.
    """
    trad = alignment["traditions"].get(tradition_id, {})
    if trad.get("absent"):
        return {}
    n = len(trad.get("tokens", []))
    result: dict[int, str] = {i: "aligned" for i in range(n)}
    for group in alignment["alignment"]:
        variant = group.get("variant", "aligned")
        for idx in group.get(tradition_id, []):
            result[idx] = variant
    return result


def render_tokens_html(alignment: dict, tradition_id: str) -> str:
    """Render a tradition's tokens as `<span class="tok {variant}">token</span>`.

    Returns a complete HTML fragment (tokens separated by spaces).
    If the tradition is marked absent, returns a placeholder fragment.
    """
    trad = alignment["traditions"].get(tradition_id, {})
    if trad.get("absent"):
        return '<p class="tok-absent"><em>absent in this tradition</em></p>'

    tokens = trad.get("tokens", [])
    variants = token_variant_map(alignment, tradition_id)
    variant_labels = {
        "aligned": "",
        "minor": "minor variant",
        "major": "major variant",
        "omitted": "omitted",
        "added": "added",
    }
    parts: list[str] = []
    for i, tok in enumerate(tokens):
        variant = variants.get(i, "aligned")
        label = variant_labels.get(variant, "")
        aria = f' aria-label="{escape(tok)} — {label}"' if label else ""
        parts.append(
            f'<span class="tok {variant}" data-idx="{i}" '
            f'data-tradition="{tradition_id}"{aria}>{escape(tok)}</span>'
        )
    return " ".join(parts)
