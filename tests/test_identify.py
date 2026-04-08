"""Tests for object identification CLI helpers."""

import json

import pytest

from astrobridge.identify import identify_object, format_identification
from astrobridge.routing.base import ObjectClass


def test_identify_star_description():
    result = identify_object("Find nearby red dwarf stars")

    assert result.object_class == ObjectClass.STAR
    assert "stellar source" in result.description.lower()
    assert result.top_catalogs[0] == "GAIA"
    assert result.search_radius_arcsec > 0


def test_identify_galaxy_description():
    result = identify_object("Search for nearby spiral galaxies")

    assert result.object_class == ObjectClass.GALAXY
    assert "galaxy" in result.description.lower()
    assert result.top_catalogs[0] == "NED"


def test_identify_unknown_description():
    result = identify_object("Something in the sky")

    assert result.object_class == ObjectClass.UNKNOWN
    assert "not confidently classified" in result.description.lower()
    assert len(result.top_catalogs) > 0


def test_identify_m31_hint():
    result = identify_object("M31")

    assert result.object_class == ObjectClass.GALAXY
    assert "andromeda" in result.description.lower()
    assert result.top_catalogs[0] == "NED"


def test_format_identification_contains_key_fields():
    result = identify_object("Find quasars at high redshift")
    output = format_identification(result)

    assert "Input:" in output
    assert "Class: quasar" in output
    assert "Recommended search radius:" in output
    assert "Top catalogs:" in output


def test_identify_json_serialization():
    result = identify_object("Find nearby red dwarf stars")
    payload = result.as_dict()

    encoded = json.dumps(payload)
    assert "star" in encoded
    assert payload["object_class"] == "star"


def test_identify_empty_input_rejected():
    with pytest.raises(ValueError):
        identify_object("   ")
