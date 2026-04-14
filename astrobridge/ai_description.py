"""AI-generated plain-language descriptions for astronomical objects.

Design
------
* ``generate_description`` is the single public function.
* It first checks the SQLite cache (``objects.ai_description``).
* On a miss it builds a prompt, calls the configured LLM, stores the result,
  and returns it.
* The LLM provider is selected via the ``AI_PROVIDER`` env variable
  (``"anthropic"`` | ``"openai"`` | ``"local"`` | ``"stub"``).
* API keys are read **only** from environment variables; they are never hard-
  coded or committed.

Environment variables
---------------------
AI_PROVIDER      : "anthropic" | "openai" | "local" | "stub"  (default: "stub")
AI_API_KEY       : API key for the selected provider
AI_MODEL         : Model name override
                   - anthropic default: "claude-haiku-4-5-20251001"
                   - openai default:    "gpt-4o-mini"
AI_BASE_URL      : Override base URL for local / OpenAI-compatible endpoints
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from typing import Optional

from astrobridge.models import UnifiedObject

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a concise, factual science communicator specialising in astronomy. "
    "Write a single short paragraph (3–5 sentences) describing the astronomical "
    "object below. Use plain English suitable for a curious undergraduate. "
    "Do not start with 'This is' or 'The object is'. "
    "Include: object type, notable physical properties, distance if available, "
    "and which catalogs identified it."
)


def _build_prompt(obj: UnifiedObject) -> str:
    """Turn a UnifiedObject into a structured prompt for the LLM."""
    lines = [
        f"Name: {obj.primary_name}",
        f"Type: {obj.object_type or 'unknown'}",
        f"RA: {obj.ra:.4f} deg,  Dec: {obj.dec:.4f} deg",
    ]
    if obj.photometry_summary:
        mags = ", ".join(
            f"{band}={mag:.2f}" for band, mag in sorted(obj.photometry_summary.items())
        )
        lines.append(f"Photometry: {mags}")
    if obj.catalog_entries:
        lines.append(f"Catalogs: {', '.join(sorted(obj.catalog_entries.keys()))}")
    if obj.alternate_names:
        lines.append(f"Also known as: {', '.join(obj.alternate_names)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM backends
# ---------------------------------------------------------------------------

def _call_openai(prompt: str, system: str, model: str, api_key: str, base_url: Optional[str]) -> str:
    """Call the OpenAI (or compatible) chat completions API."""
    try:
        import openai  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "openai package is required for AI_PROVIDER=openai.  "
            "Install with: pip install openai"
        ) from exc

    kwargs: dict = {"api_key": api_key, "model": model}
    if base_url:
        kwargs["base_url"] = base_url
    client = openai.OpenAI(**{k: v for k, v in kwargs.items() if k != "model"})
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=256,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def _call_anthropic(prompt: str, system: str, model: str, api_key: str, _base: Optional[str]) -> str:
    """Call the Anthropic Claude API."""
    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package is required for AI_PROVIDER=anthropic.  "
            "Install with: pip install anthropic"
        ) from exc

    client = anthropic.Anthropic(api_key=api_key or None)
    message = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _call_stub(prompt: str, _system: str, _model: str, _key: str, _base: Optional[str]) -> str:
    """Return a deterministic placeholder (no network required)."""
    obj_line = next((line for line in prompt.splitlines() if line.startswith("Name:")), "")
    name = obj_line.replace("Name:", "").strip() or "this object"
    type_line = next((line for line in prompt.splitlines() if line.startswith("Type:")), "")
    obj_type = type_line.replace("Type:", "").strip() or "astronomical object"
    return (
        f"{name} is a {obj_type} catalogued in AstroBridge. "
        "Detailed AI descriptions require a configured AI_PROVIDER and API key. "
        "Set AI_PROVIDER=openai and AI_API_KEY in your environment to enable "
        "rich, LLM-generated summaries."
    )


_BACKENDS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "local": _call_openai,   # same OpenAI-compatible interface, different base_url
    "stub": _call_stub,
}

_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "local": "stub",
    "stub": "stub",
}


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(obj: UnifiedObject) -> str:
    """Stable cache key based on object name + coordinates."""
    raw = f"{obj.primary_name}|{obj.ra:.6f}|{obj.dec:.6f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _fetch_cached(conn: sqlite3.Connection, obj_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT ai_description FROM objects WHERE id = ?", (obj_id,)
    ).fetchone()
    if row and row[0]:
        return str(row[0])
    return None


def _store_cached(conn: sqlite3.Connection, obj_id: str, description: str) -> None:
    from astrobridge.database import update_ai_description
    update_ai_description(conn, obj_id, description)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_description(
    obj: UnifiedObject,
    conn: Optional[sqlite3.Connection] = None,
    force_refresh: bool = False,
) -> str:
    """Generate (or retrieve from cache) a plain-language object description.

    Parameters
    ----------
    obj :
        The unified object to describe.
    conn :
        Open SQLite connection used for caching.  Pass ``None`` to disable
        caching (descriptions are generated every call).
    force_refresh :
        If True, skip the cache lookup and always call the LLM.

    Returns
    -------
    str
        Human-readable description paragraph.
    """
    obj_id = _cache_key(obj)

    # 1. Cache read
    if conn is not None and not force_refresh:
        cached = _fetch_cached(conn, obj_id)
        if cached:
            logger.debug("AI description cache hit for %s", obj.primary_name)
            return cached

    # 2. Select backend
    provider = os.getenv("AI_PROVIDER", "stub").lower()
    backend = _BACKENDS.get(provider, _call_stub)
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", _DEFAULT_MODELS.get(provider, "stub"))
    base_url = os.getenv("AI_BASE_URL") or None

    # 3. Call LLM
    prompt = _build_prompt(obj)
    try:
        description = backend(prompt, _SYSTEM_PROMPT, model, api_key, base_url)
    except Exception as exc:
        logger.error(
            "AI description generation failed for %s: %s", obj.primary_name, exc
        )
        description = _call_stub(prompt, _SYSTEM_PROMPT, model, api_key, base_url)

    # 4. Cache write
    if conn is not None:
        try:
            _store_cached(conn, obj_id, description)
        except Exception as exc:
            logger.warning("Failed to cache AI description: %s", exc)

    return description
