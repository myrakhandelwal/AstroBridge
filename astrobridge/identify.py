"""Command-line object identification helpers."""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Optional

from astrobridge.models import UnifiedObject
from astrobridge.routing import NLPQueryRouter
from astrobridge.routing.base import CatalogType, ObjectClass
from astrobridge.routing.intelligent import CatalogRanker

OBJECT_DESCRIPTIONS: dict[ObjectClass, str] = {
    ObjectClass.STAR: "This looks like a stellar source: a point-like object such as a dwarf, giant, or binary star.",
    ObjectClass.GALAXY: "This looks like a galaxy: an extended extragalactic system containing many stars, gas, and dust.",
    ObjectClass.QUASAR: "This looks like a quasar: an extremely luminous active galactic nucleus powered by a supermassive black hole.",
    ObjectClass.AGN: "This looks like an active galactic nucleus: a compact galaxy core with energetic accretion activity.",
    ObjectClass.NEBULA: "This looks like a nebula: a diffuse cloud of gas and dust, often associated with star formation or stellar death.",
    ObjectClass.CLUSTER: "This looks like a cluster: a grouped stellar system or cluster-scale structure that should be checked for membership and context.",
    ObjectClass.SNE: "This looks like a supernova or transient event: a short-lived explosive or variable phenomenon.",
    ObjectClass.UNKNOWN: "This target is not confidently classified from the text alone, so the router falls back to balanced catalog selection.",
}


KNOWN_DESIGNATION_HINTS: dict[str, tuple[ObjectClass, str]] = {
    "m31": (ObjectClass.GALAXY, "M31 is the Andromeda Galaxy, a nearby spiral galaxy in the Local Group."),
    "andromedagalaxy": (ObjectClass.GALAXY, "The Andromeda Galaxy is a nearby spiral galaxy and one of the closest large galaxies to the Milky Way."),
    "m51": (ObjectClass.GALAXY, "M51 is the Whirlpool Galaxy, a classic interacting spiral galaxy."),
    "m42": (ObjectClass.NEBULA, "M42 is the Orion Nebula, a bright star-forming emission nebula."),
    "m1": (ObjectClass.NEBULA, "M1 is the Crab Nebula, a supernova remnant in Taurus."),
    "m13": (ObjectClass.CLUSTER, "M13 is the Hercules Globular Cluster, a dense stellar cluster."),
    "m45": (ObjectClass.CLUSTER, "M45 is the Pleiades, a nearby open cluster."),
    "proximacentauri": (ObjectClass.STAR, "Proxima Centauri is the nearest known star to the Sun, a red dwarf in the Alpha Centauri system."),
    "sirius": (ObjectClass.STAR, "Sirius is the brightest star in the night sky and a nearby stellar system."),
    "betelgeuse": (ObjectClass.STAR, "Betelgeuse is a red supergiant star in the Orion constellation."),
}


DEFAULT_SEARCH_RADII = {
    ObjectClass.STAR: 10.0,
    ObjectClass.GALAXY: 30.0,
    ObjectClass.QUASAR: 10.0,
    ObjectClass.AGN: 20.0,
    ObjectClass.NEBULA: 90.0,
    ObjectClass.CLUSTER: 120.0,
    ObjectClass.SNE: 15.0,
    ObjectClass.UNKNOWN: 60.0,
}


def _catalog_label(catalog: CatalogType) -> str:
    """Format catalog type as uppercase label.
    
    Args:
        catalog: Catalog type to format.
        
    Returns:
        Uppercase catalog name string.
    """
    return catalog.value.upper()


@dataclass(frozen=True)
class IdentificationResult:
    """Human-readable identification result for a target input."""

    input_text: str
    object_class: ObjectClass
    description: str
    search_radius_arcsec: float
    top_catalogs: list[str]
    reasoning: str

    def as_dict(self) -> dict[str, object]:
        return {
            "input_text": self.input_text,
            "object_class": self.object_class.value,
            "description": self.description,
            "search_radius_arcsec": self.search_radius_arcsec,
            "top_catalogs": self.top_catalogs,
            "reasoning": self.reasoning,
        }


def identify_object(input_text: str, router: Optional[NLPQueryRouter] = None) -> IdentificationResult:
    """Classify an object or query string and generate a short explanation.
    
    Combines built-in designation hints (for common targets like M31, Proxima Centauri)
    with NLP routing logic. Falls back to general-purpose catalog ordering for unknown objects.
    
    Args:
        input_text: Target designation or query (e.g., 'M31', 'Find red dwarfs').
        router: Optional NLPQueryRouter; creates default router if not provided.
        
    Returns:
        IdentificationResult with object class, description, search radius, and catalogs.
        
    Raises:
        ValueError: If input_text is empty or whitespace-only.
    """
    normalized = input_text.strip()
    if not normalized:
        raise ValueError("input_text must not be empty")

    router = router or NLPQueryRouter()

    normalized_designation = "".join(ch.lower() for ch in normalized if ch.isalnum())
    hint = KNOWN_DESIGNATION_HINTS.get(normalized_designation)

    if hint is not None:
        object_class, description = hint
        ranking = CatalogRanker.rank_for_class(object_class, {})
        catalogs = [_catalog_label(catalog) for catalog, _ in ranking[:3]]
        reasoning = f"Recognized {normalized} as a known {object_class.value} target from a built-in designation hint."
        search_radius_arcsec = DEFAULT_SEARCH_RADII.get(object_class, 60.0)
    else:
        decision = router.parse_query(normalized)
        object_class = decision.object_class
        description = OBJECT_DESCRIPTIONS.get(object_class, OBJECT_DESCRIPTIONS[ObjectClass.UNKNOWN])
        catalogs = [_catalog_label(catalog) for catalog in decision.get_top_catalogs(3)]
        reasoning = decision.reasoning
        search_radius_arcsec = decision.search_radius_arcsec

        if object_class == ObjectClass.UNKNOWN:
            description = (
                f"{description} The query still provides useful context, so AstroBridge will prioritize "
                f"{', '.join(catalogs[:2]) if catalogs else 'general-purpose catalogs'} for a first pass."
            )
        else:
            description = (
                f"{description} For this target type, AstroBridge prioritizes {', '.join(catalogs[:2]) if catalogs else 'general-purpose catalogs'}."
            )

    return IdentificationResult(
        input_text=normalized,
        object_class=object_class,
        description=description,
        search_radius_arcsec=search_radius_arcsec,
        top_catalogs=catalogs,
        reasoning=reasoning,
    )


def format_identification(result: IdentificationResult) -> str:
    """Format an identification result for terminal output.
    
    Produces a human-readable multi-line summary of object classification,
    recommended search strategy, and top catalogs.
    
    Args:
        result: IdentificationResult from identify_object().
        
    Returns:
        Formatted string summary ready for console output.
    """
    top_catalogs = ", ".join(result.top_catalogs) if result.top_catalogs else "none"
    lines = [
        f"Input: {result.input_text}",
        f"Class: {result.object_class.value}",
        f"Description: {result.description}",
        f"Recommended search radius: {result.search_radius_arcsec:.1f} arcsec",
        f"Top catalogs: {top_catalogs}",
        f"Reasoning: {result.reasoning}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for object identification."""
    parser = argparse.ArgumentParser(
        prog="astrobridge-identify",
        description="Identify an astronomical object or describe what a query is pointing to.",
    )
    parser.add_argument(
        "query",
        nargs="+",
        help="Object name or natural-language description to analyze",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of formatted text",
    )
    return parser


async def identify_from_catalogs(
    input_text: str,
    router: Optional[NLPQueryRouter] = None,
    ai_description: bool = True,
    timeout_sec: float = 10.0,
) -> dict[str, object]:
    """Identify a celestial object by querying live catalogs.

    Combines NLP routing (to classify the query and rank catalogs) with a live
    fan-out to SIMBAD and NED.  Returns a plain dict suitable for JSON responses.

    Parameters
    ----------
    input_text :
        Object name or natural-language query (e.g. ``"M31"``, ``"red dwarfs"``).
    router :
        Optional pre-built NLPQueryRouter; a default one is created if omitted.
    ai_description :
        If True, generate a plain-language description via ``ai_description.py``.
    timeout_sec :
        Per-catalog network timeout.

    Returns
    -------
    dict with keys:
        input_text, object_class, description, search_radius_arcsec,
        top_catalogs, reasoning, catalog_data (UnifiedObject dict or None)
    """
    from astrobridge.ai_description import generate_description
    from astrobridge.lookup import lookup_object

    def _ai_description_is_configured() -> bool:
        """Return True when AI settings indicate a real backend is usable."""
        provider = os.getenv("AI_PROVIDER", "stub").strip().lower()
        if provider == "stub":
            return False
        if provider in {"openai", "anthropic"}:
            return bool(os.getenv("AI_API_KEY", "").strip())
        if provider == "local":
            return bool(os.getenv("AI_BASE_URL", "").strip())
        return False

    # 1. NLP classification (fast, no network)
    base = identify_object(input_text, router=router)

    # 2. Live catalog lookup
    unified: Optional[UnifiedObject] = await lookup_object(input_text, timeout_sec=timeout_sec)

    # 3. Build description
    if unified is not None and ai_description and _ai_description_is_configured():
        description = generate_description(unified, conn=None)
    else:
        description = base.description

    catalog_data: Optional[dict[str, object]] = None
    if unified is not None:
        catalog_data = {
            "primary_name": unified.primary_name,
            "ra": unified.ra,
            "dec": unified.dec,
            "object_type": unified.object_type,
            "photometry": unified.photometry_summary,
            "catalogs": list(unified.catalog_entries.keys()) if unified.catalog_entries else [],
            "alternate_names": unified.alternate_names,
        }

    return {
        "input_text": base.input_text,
        "object_class": base.object_class.value,
        "description": description,
        "search_radius_arcsec": base.search_radius_arcsec,
        "top_catalogs": base.top_catalogs,
        "reasoning": base.reasoning,
        "catalog_data": catalog_data,
    }


def main(argv: Optional[list[str]] = None) -> None:
    """Entry point for the astrobridge-identify command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    query_text = " ".join(args.query)
    result = identify_object(query_text)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return

    print(format_identification(result))


if __name__ == "__main__":
    main()
