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


@pytest.mark.parametrize("title", ["<!--<script>", "<!-- x -->", "a & b > c", "</SCRIPT >"])
def test_render_data_never_contains_raw_html_specials(title):
    html = pd.render_placement_dials(CHART, title=title)
    for name in ("CONTENT", "CHART"):
        line = re.search(r"var %s = (.*);\n" % name, html).group(1)
        assert "<" not in line and ">" not in line and "&" not in line
    assert json.loads(re.search(r"var CHART = (.*);\n", html).group(1))["title"] == title


# ---------------------------------------------------------------------------
# Packaged content and template
# ---------------------------------------------------------------------------

def test_content_file_is_complete_and_matches_planet_and_sign_order():
    c = pd.load_content()
    assert [p["name"] for p in c["planets"]] == pd.PLANET_ORDER
    assert [s["name"] for s in c["signs"]] == pd.SIGN_NAMES
    assert len(c["houses"]) == 12 and all(c["houses"])
    assert len(c["rulers"]) == 12 and set(c["rulers"]) <= set(pd.PLANET_ORDER)
    assert len(c["rulers_traditional"]) == 12 and set(c["rulers_traditional"]) <= set(pd.PLANET_ORDER)
    # The two lists may differ only where a modern planet took a sign over.
    differing = {pd.SIGN_NAMES[i] for i in range(12) if c["rulers"][i] != c["rulers_traditional"][i]}
    assert differing == {"Scorpio", "Aquarius", "Pisces"}
    # Whoever the page names as ruler must be at home there in the dignity table.
    for i, sign in enumerate(pd.SIGN_NAMES):
        for ruler in {c["rulers"][i], c["rulers_traditional"][i]}:
            assert sign in c["dignity"][ruler]["domicile"], (sign, ruler)
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


def test_output_must_be_an_html_file(tmp_path):
    for bad in (".zshrc", "notes.md", "script.py", "noextension"):
        with pytest.raises(pd.PlacementDialsError, match=r"\.html"):
            pd.resolve_output_path(str(tmp_path / bad))
        assert not (tmp_path / bad).exists()
    assert pd.resolve_output_path(str(tmp_path / "A.HTM")).name == "A.HTM"


def test_refused_path_leaves_an_existing_file_untouched(tmp_path):
    victim = tmp_path / ".zshrc"
    victim.write_text("export PATH=1")
    with pytest.raises(pd.PlacementDialsError):
        pd.create_placement_dials(CHART, output_path=str(victim))
    assert victim.read_text() == "export PATH=1"


def test_default_file_is_named_after_the_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    mine = pd.resolve_output_path(profile_name="Todd")
    liz = pd.resolve_output_path(profile_name="Liz", profile_id=3)
    assert mine.name == "placement_dials_todd.html"
    assert liz.name == "placement_dials_liz.html" and liz.parent == mine.parent == (tmp_path / "Downloads").resolve()
    folder = tmp_path / "out"
    folder.mkdir()
    assert pd.resolve_output_path(str(folder), profile_name="Liz").name == "placement_dials_liz.html"
    explicit = tmp_path / "mine.html"
    assert pd.resolve_output_path(str(explicit), profile_name="Liz") == explicit.resolve()


@pytest.mark.parametrize("name,pid,expected", [
    ("Liz W.", 2, "placement_dials_liz_w.html"),
    ("  José  Núñez ", None, "placement_dials_jose_nunez.html"),
    ("../../etc/passwd", None, "placement_dials_etc_passwd.html"),
    ("🌙", 5, "placement_dials_profile5.html"),
    ("", 5, "placement_dials_profile5.html"),
    (None, None, "placement_dials.html"),
    ("x" * 100, None, "placement_dials_" + "x" * 40 + ".html"),
])
def test_default_file_name_is_safe_and_has_fallbacks(name, pid, expected):
    assert pd.default_file_name(name, pid) == expected


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

@pytest.fixture(autouse=True)
def _no_real_profile_lookup(monkeypatch):
    """Handler tests never touch the real database for the profile name."""
    monkeypatch.setattr(server, "get_profile_name", lambda profile_id=None: "Todd")


@pytest.mark.asyncio
async def test_handler_names_the_default_file_after_the_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    seen = []
    monkeypatch.setattr(server, "get_profile_name", lambda profile_id=None: seen.append(profile_id) or "Liz")
    with patch.object(server, "get_natal_chart_data", return_value=CHART):
        result = await server.handle_visualize_placement_dials({"profile_id": 3})
    assert seen == [3]
    assert (tmp_path / "Downloads" / "placement_dials_liz.html").exists()
    assert "placement_dials_liz.html" in result[0].text


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
    assert set(tool.inputSchema["properties"]) == {"output_path", "title", "profile_id", "open_in_browser"}
    assert tool.inputSchema["properties"]["open_in_browser"]["type"] == "boolean"
    assert "required" not in tool.inputSchema


def test_tool_carries_the_stored_chart_data_notice():
    assert "visualize_placement_dials" in server.NATAL_NOTICE_TOOLS


# ---------------------------------------------------------------------------
# Opening the page in a browser
# ---------------------------------------------------------------------------

def test_open_in_default_browser_passes_a_file_uri(monkeypatch, tmp_path):
    monkeypatch.setenv("DISPLAY", ":0")  # a desktop session, so Linux CI behaves like a Mac
    page = tmp_path / "dials.html"
    page.write_text("x")
    with patch.object(pd.webbrowser, "open", return_value=True) as opener:
        assert pd.open_in_default_browser(str(page)) is True
    opener.assert_called_once_with(page.resolve().as_uri())


def test_open_in_default_browser_reports_false_instead_of_raising(monkeypatch, tmp_path):
    monkeypatch.setenv("DISPLAY", ":0")  # a desktop session, so Linux CI behaves like a Mac
    with patch.object(pd.webbrowser, "open", return_value=False):
        assert pd.open_in_default_browser(str(tmp_path / "a.html")) is False
    with patch.object(pd.webbrowser, "open", side_effect=RuntimeError("no display")):
        assert pd.open_in_default_browser(str(tmp_path / "a.html")) is False


def test_open_in_default_browser_skips_headless_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(pd.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with patch.object(pd.webbrowser, "open", return_value=True) as opener:
        assert pd.open_in_default_browser(str(tmp_path / "a.html")) is False
    opener.assert_not_called()
    monkeypatch.setenv("DISPLAY", ":0")
    with patch.object(pd.webbrowser, "open", return_value=True) as opener:
        assert pd.open_in_default_browser(str(tmp_path / "a.html")) is True
    opener.assert_called_once()


@pytest.mark.asyncio
async def test_handler_reports_a_bad_output_path(tmp_path):
    with patch.object(server, "get_natal_chart_data", return_value=CHART):
        result = await server.handle_visualize_placement_dials({"output_path": str(tmp_path / ".zshrc")})
    assert result[0].text.startswith("Error:") and ".html" in result[0].text


@pytest.mark.asyncio
async def test_handler_does_not_open_a_browser_unless_asked(tmp_path):
    with patch.object(server, "get_natal_chart_data", return_value=CHART), \
         patch.object(server, "open_in_default_browser") as opener:
        result = await server.handle_visualize_placement_dials({"output_path": str(tmp_path / "d.html")})
    opener.assert_not_called()
    assert "Open it in a browser" in result[0].text


@pytest.mark.asyncio
async def test_handler_opens_the_page_when_asked(tmp_path):
    out = tmp_path / "d.html"
    with patch.object(server, "get_natal_chart_data", return_value=CHART), \
         patch.object(server, "open_in_default_browser", return_value=True) as opener:
        result = await server.handle_visualize_placement_dials({"output_path": str(out), "open_in_browser": True})
    opener.assert_called_once_with(str(out.resolve()))
    assert "Opened in your default browser" in result[0].text


@pytest.mark.asyncio
async def test_handler_says_so_when_the_browser_cannot_be_opened(tmp_path):
    with patch.object(server, "get_natal_chart_data", return_value=CHART), \
         patch.object(server, "open_in_default_browser", return_value=False):
        result = await server.handle_visualize_placement_dials(
            {"output_path": str(tmp_path / "d.html"), "open_in_browser": True}
        )
    assert "Could not open a browser" in result[0].text
    assert "Saved to:" in result[0].text
