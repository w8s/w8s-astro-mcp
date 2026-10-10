"""Tests for visualize_placement_dials: house assignment, template filling, output paths,
the packaged content file, and the extracted handler."""

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from w8s_astro_mcp import server
from w8s_astro_mcp.tools import placement_dials as pd
from w8s_astro_mcp.utils.ephemeris import EphemerisError


# ---------------------------------------------------------------------------
# Test data: equal houses from a Capricorn Ascendant, so house 1 starts at
# 20.879 Capricorn and the wheel wraps past 0 Aries inside house 3.
# ---------------------------------------------------------------------------

ASC = 270 + 20.879


def _equal_house_chart(planets):
    houses = {}
    for n in range(1, 13):
        pos = (ASC + 30 * (n - 1)) % 360
        houses[str(n)] = {"sign": pd.SIGN_NAMES[int(pos // 30)], "degree": pos % 30}
    return {"planets": planets, "houses": houses, "points": {}}


PLANETS = {
    "Sun": {"sign": "Taurus", "degree": 15.6},
    "Moon": {"sign": "Gemini", "degree": 14.98},
    "Mercury": {"sign": "Taurus", "degree": 25.59},
    "Venus": {"sign": "Taurus", "degree": 23.13},
    "Mars": {"sign": "Taurus", "degree": 8.16},
    "Jupiter": {"sign": "Libra", "degree": 1.14},
    "Saturn": {"sign": "Libra", "degree": 3.73},
    "Uranus": {"sign": "Scorpio", "degree": 28.64},
    "Neptune": {"sign": "Sagittarius", "degree": 24.45},
    "Pluto": {"sign": "Libra", "degree": 22.33},
}
CHART = _equal_house_chart(PLANETS)


# ---------------------------------------------------------------------------
# House assignment
# ---------------------------------------------------------------------------

def _cusps():
    return [(ASC + 30 * i) % 360 for i in range(12)]


def test_house_of_handles_wraparound():
    # Houses start at 290.879, 320.879, 350.879, 20.879 (Aries), ... so house 3 crosses 0 Aries.
    assert pd.house_of(355, _cusps()) == 3
    assert pd.house_of(0.5, _cusps()) == 3
    assert pd.house_of(38.16, _cusps()) == 4     # 8.16 Taurus


def test_house_of_cusp_belongs_to_the_house_it_starts():
    cusps = _cusps()
    assert pd.house_of(cusps[3], cusps) == 4
    assert pd.house_of(ASC, cusps) == 1
    assert pd.house_of(ASC - 0.01, cusps) == 12


def test_absolute_position_rejects_unknown_sign():
    with pytest.raises(pd.PlacementDialsError):
        pd.absolute_position("Ophiuchus", 3)


# ---------------------------------------------------------------------------
# Chart data
# ---------------------------------------------------------------------------

def test_build_chart_data_shape_and_values():
    data = pd.build_chart_data(CHART, title="Todd")
    assert data["title"] == "Todd"
    assert len(data["cusps"]) == 12
    assert data["cusps"][0] == pd.SIGN_NAMES.index("Capricorn")
    assert len(data["placements"]) == 10
    mars = [p for p in data["placements"] if p[0] == pd.PLANET_ORDER.index("Mars")][0]
    assert mars == [4, pd.SIGN_NAMES.index("Taurus"), 4]


def test_build_chart_data_skips_missing_planets():
    chart = _equal_house_chart({"Sun": PLANETS["Sun"], "Mars": PLANETS["Mars"]})
    data = pd.build_chart_data(chart)
    assert [p[0] for p in data["placements"]] == [0, 4]


def test_build_chart_data_requires_all_house_cusps():
    chart = _equal_house_chart(PLANETS)
    del chart["houses"]["7"]
    with pytest.raises(pd.PlacementDialsError, match="house"):
        pd.build_chart_data(chart)


def test_build_chart_data_requires_planets():
    with pytest.raises(pd.PlacementDialsError, match="planet"):
        pd.build_chart_data(_equal_house_chart({}))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_render_fills_both_slots_and_embeds_chart_data():
    html = pd.render_placement_dials(CHART, title="Natal placements")
    assert html.startswith("<!doctype html>")
    assert "$content_json" not in html and "$chart_json" not in html
    embedded = re.search(r"var CHART = (.*);\n", html).group(1)
    assert json.loads(embedded) == pd.build_chart_data(CHART, "Natal placements")


def test_render_keeps_title_from_breaking_out_of_the_script():
    hostile = "</script><script>alert(1)</script>"
    html = pd.render_placement_dials(CHART, title=hostile)
    assert html.count("</script>") == 1
    embedded = re.search(r"var CHART = (.*);\n", html).group(1)
    assert json.loads(embedded)["title"] == hostile


# ---------------------------------------------------------------------------
# Packaged content and template
# ---------------------------------------------------------------------------

def test_content_file_is_complete_and_matches_planet_and_sign_order():
    c = pd.load_content()
    assert [p["name"] for p in c["planets"]] == pd.PLANET_ORDER
    assert [s["name"] for s in c["signs"]] == pd.SIGN_NAMES
    assert len(c["houses"]) == 12 and all(c["houses"])
    assert len(c["rulers"]) == 12 and set(c["rulers"]) <= set(pd.PLANET_ORDER)
    assert len(c["angularity"]) == 3
    assert {s["element"] for s in c["signs"]} == {"fire", "earth", "air", "water"}
    assert set(c["element_text"]) == {"fire", "earth", "air", "water"}
    assert set(c["mode_text"]) == {s["mode"] for s in c["signs"]}
    assert list(c["dignity"]) == pd.PLANET_ORDER
    for planet in c["planets"]:
        assert all(planet[k] for k in ("glyph", "does", "core", "keywords"))
    for sign in c["signs"]:
        assert sign["manner"]


def test_template_and_content_ship_inside_the_package():
    from importlib import resources

    base = resources.files("w8s_astro_mcp").joinpath("templates")
    assert base.joinpath("placement_dials.html").is_file()
    assert base.joinpath("placement_dials_content.json").is_file()


def test_template_has_only_its_two_slots():
    from importlib import resources

    text = resources.files("w8s_astro_mcp").joinpath("templates", "placement_dials.html").read_text(encoding="utf-8")
    assert sorted(re.findall(r"\$\w+", text)) == ["$chart_json", "$content_json"]


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def test_default_output_path_is_downloads(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert pd.resolve_output_path() == (tmp_path / "Downloads" / "placement_dials.html").resolve()


def test_folder_gets_the_default_file_name(tmp_path):
    existing = tmp_path / "vault"
    existing.mkdir()
    assert pd.resolve_output_path(str(existing)) == (existing / "placement_dials.html").resolve()
    assert pd.resolve_output_path(str(tmp_path / "new") + "/") == (tmp_path / "new" / "placement_dials.html").resolve()


def test_file_path_is_kept(tmp_path):
    target = tmp_path / "mine.html"
    assert pd.resolve_output_path(str(target)) == target.resolve()


def test_create_writes_file_and_makes_folders_and_overwrites(tmp_path):
    target = tmp_path / "a" / "b" / "dials.html"
    saved = pd.create_placement_dials(CHART, output_path=str(target))
    assert Path(saved) == target.resolve()
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")
    target.write_text("old")
    pd.create_placement_dials(CHART, output_path=str(target))
    assert target.read_text(encoding="utf-8") != "old"


# ---------------------------------------------------------------------------
# Server wiring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handler_success_writes_file(tmp_path):
    out = tmp_path / "dials.html"
    with patch.object(server, "get_natal_chart_data", return_value=CHART) as get_chart:
        result = await server.handle_visualize_placement_dials({"output_path": str(out), "profile_id": 7})
    get_chart.assert_called_once_with(profile_id=7)
    assert "Saved to:" in result[0].text and str(out.resolve()) in result[0].text
    assert out.exists()


@pytest.mark.asyncio
async def test_handler_reports_errors_as_text():
    with patch.object(server, "get_natal_chart_data", side_effect=EphemerisError("Owner profile not configured.")):
        result = await server.handle_visualize_placement_dials({})
    assert result[0].text.startswith("Error:") and "Owner profile" in result[0].text


@pytest.mark.asyncio
async def test_tool_is_listed_with_expected_inputs():
    tools = {t.name: t for t in await server.list_tools()}
    tool = tools["visualize_placement_dials"]
    assert set(tool.inputSchema["properties"]) == {"output_path", "title", "profile_id"}
    assert "required" not in tool.inputSchema


def test_tool_carries_the_stored_chart_data_notice():
    assert "visualize_placement_dials" in server.NATAL_NOTICE_TOOLS
