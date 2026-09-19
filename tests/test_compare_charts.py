"""Tests for compare_charts: aspect motion (applying/separating), chart labels,
include_angles, text/JSON formatting, and handle_compare_charts.

Regression fixtures are frozen from real data for 2026-09-19 09:00 UT against the
natal chart born 1981-05-06.  Planet speeds are in degrees/day (negative = retrograde).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from w8s_astro_mcp.tools.analysis_tools import (
    AnalysisError,
    aspect_motion,
    chart_labels,
    compare_charts,
    format_aspect_json,
    format_aspect_report,
    signed_separation,
)


# ---------------------------------------------------------------------------
# Fixtures (frozen real data, 2026-09-19 09:00 UT)
# ---------------------------------------------------------------------------

NATAL = {
    "planets": {
        "Neptune": {"degree": 24.45, "sign": "Sagittarius"},
        "Mercury": {"degree": 25.16, "sign": "Taurus"},
        "Moon": {"degree": 11.86, "sign": "Gemini"},
        "Saturn": {"degree": 3.74, "sign": "Libra"},
    },
    "points": {
        "Ascendant": {"degree": 14.96, "sign": "Scorpio"},
        "MC": {"degree": 23.71, "sign": "Leo"},
    },
    "metadata": {"date": "1981-05-06", "time": "00:50:00"},
}

TRANSIT = {
    "planets": {
        "Mars": {"degree": 24.79, "sign": "Cancer", "speed": 0.60},
        "Saturn": {"degree": 12.47, "sign": "Aries", "speed": -0.08},
        "Neptune": {"degree": 3.18, "sign": "Aries", "speed": -0.02},
        "Jupiter": {"degree": 17.42, "sign": "Leo", "speed": 0.20},
    },
    "points": {
        "Ascendant": {"degree": 15.04, "sign": "Leo"},
        "MC": {"degree": 8.94, "sign": "Taurus"},
    },
    "metadata": {"date": "2026-09-19", "time": "09:00:00"},
}

NATAL_META = {"kind": "natal"}
TRANSIT_META = {"kind": "transit"}


def _compare(**kwargs):
    kwargs.setdefault("orb_multiplier", 0.6)
    return compare_charts(
        NATAL, TRANSIT, chart1_meta=NATAL_META, chart2_meta=TRANSIT_META, **kwargs
    )


def _find(result, body1, body2):
    """Return the single aspect between body1 (chart1) and body2 (chart2)."""
    hits = [a for a in result["aspects"] if a["body1"] == body1 and a["body2"] == body2]
    assert len(hits) == 1, f"expected exactly one {body1}/{body2} aspect, got {len(hits)}"
    return hits[0]


# ---------------------------------------------------------------------------
# signed_separation
# ---------------------------------------------------------------------------

class TestSignedSeparation:
    def test_simple(self):
        assert signed_separation(10, 30) == pytest.approx(20)
        assert signed_separation(30, 10) == pytest.approx(-20)

    def test_wraps_forward_across_zero(self):
        assert signed_separation(350, 10) == pytest.approx(20)

    def test_wraps_backward_across_zero(self):
        assert signed_separation(10, 350) == pytest.approx(-20)

    def test_half_circle_is_positive_180(self):
        assert signed_separation(0, 180) == pytest.approx(180)
        assert signed_separation(180, 0) == pytest.approx(180)


# ---------------------------------------------------------------------------
# aspect_motion (pure helper)
# ---------------------------------------------------------------------------

class TestAspectMotion:
    def test_conjunction_applying(self):
        applying, days = aspect_motion(100, None, 98, 1.0, 0)
        assert applying is True
        assert days == pytest.approx(2.0)

    def test_conjunction_separating(self):
        applying, days = aspect_motion(100, None, 102, 1.0, 0)
        assert applying is False
        assert days == pytest.approx(-2.0)

    def test_retrograde_body_applies_when_moving_toward_exact(self):
        applying, days = aspect_motion(100, None, 102, -1.0, 0)
        assert applying is True
        assert days == pytest.approx(2.0)

    def test_retrograde_body_separates_when_moving_away(self):
        applying, days = aspect_motion(100, None, 98, -1.0, 0)
        assert applying is False
        assert days == pytest.approx(-2.0)

    def test_wrap_around_zero_separating(self):
        applying, days = aspect_motion(359, None, 1, 1.0, 0)
        assert applying is False
        assert days == pytest.approx(-2.0)

    def test_wrap_around_zero_applying(self):
        applying, days = aspect_motion(359, None, 358, 1.0, 0)
        assert applying is True
        assert days == pytest.approx(1.0)

    def test_opposition_applying_across_180(self):
        applying, days = aspect_motion(0, None, 179, 0.5, 180)
        assert applying is True
        assert days == pytest.approx(2.0)

    def test_opposition_separating_across_180(self):
        applying, days = aspect_motion(0, None, 181, 0.5, 180)
        assert applying is False
        assert days == pytest.approx(-2.0)

    def test_sextile_applying_positive_separation(self):
        applying, days = aspect_motion(0, None, 58, 1.0, 60)
        assert applying is True
        assert days == pytest.approx(2.0)

    def test_sextile_applying_negative_separation(self):
        applying, days = aspect_motion(0, None, 302, -1.0, 60)
        assert applying is True
        assert days == pytest.approx(2.0)

    def test_moving_body1_with_fixed_body2(self):
        applying, days = aspect_motion(98, 1.0, 100, None, 0)
        assert applying is True
        assert days == pytest.approx(2.0)

    def test_both_moving_uses_relative_speed(self):
        # body2 is 2 degrees ahead, but body1 is faster by 1 deg/day -> closing
        applying, days = aspect_motion(100, 3.0, 102, 2.0, 0)
        assert applying is True
        assert days == pytest.approx(2.0)

    def test_no_speeds_gives_none(self):
        assert aspect_motion(100, None, 98, None, 0) == (None, None)

    def test_equal_speeds_give_none(self):
        assert aspect_motion(100, 1.0, 98, 1.0, 0) == (None, None)

    def test_near_stationary_gives_none(self):
        assert aspect_motion(100, None, 98, 0.0005, 0) == (None, None)

    def test_exact_reports_zero_days_and_no_direction(self):
        applying, days = aspect_motion(100, None, 100, 1.0, 0)
        assert applying is None
        assert days == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# chart_labels
# ---------------------------------------------------------------------------

class TestChartLabels:
    def test_natal_and_transit(self):
        assert chart_labels({"kind": "natal"}, {"kind": "transit"}) == ("natal", "transit")

    def test_missing_meta_falls_back_to_chart_numbers(self):
        assert chart_labels(None, None) == ("chart 1", "chart 2")

    def test_event_label_is_kept(self):
        assert chart_labels({"kind": "natal"}, {"kind": "event:full-moon"}) == (
            "natal",
            "event:full-moon",
        )

    def test_synastry_uses_profile_names(self):
        left = {"kind": "natal", "name": "Todd"}
        right = {"kind": "natal", "name": "Liz"}
        assert chart_labels(left, right) == ("natal (Todd)", "natal (Liz)")

    def test_synastry_without_names_uses_chart_numbers(self):
        assert chart_labels({"kind": "natal"}, {"kind": "natal"}) == (
            "natal, chart 1",
            "natal, chart 2",
        )

    def test_synastry_with_identical_names_uses_chart_numbers(self):
        left = {"kind": "natal", "name": "Todd"}
        right = {"kind": "natal", "name": "Todd"}
        assert chart_labels(left, right) == ("natal, chart 1", "natal, chart 2")


# ---------------------------------------------------------------------------
# compare_charts: regression fixtures from real 2026-09-19 data
# ---------------------------------------------------------------------------

class TestRealDataRegression:
    def test_mars_quincunx_natal_neptune_is_separating(self):
        a = _find(_compare(), "Neptune", "Mars")
        assert a["aspect"] == "quincunx"
        assert a["orb"] == pytest.approx(0.34, abs=0.005)
        assert a["applying"] is False
        assert a["days_to_exact"] == pytest.approx(-0.567, abs=0.005)
        assert a["exact_utc"] == "2026-09-18T19:24:00Z"

    def test_mars_sextile_natal_mercury_is_applying(self):
        a = _find(_compare(), "Mercury", "Mars")
        assert a["aspect"] == "sextile"
        assert a["applying"] is True
        assert a["days_to_exact"] == pytest.approx(0.617, abs=0.005)
        assert a["exact_utc"] == "2026-09-19T23:48:00Z"

    def test_saturn_sextile_natal_moon_applies_while_retrograde(self):
        a = _find(_compare(), "Moon", "Saturn")
        assert a["aspect"] == "sextile"
        assert a["applying"] is True
        assert a["days_to_exact"] == pytest.approx(7.625, abs=0.05)
        assert a["exact_utc"] == "2026-09-27T00:00:00Z"

    def test_neptune_opposition_natal_saturn_is_separating(self):
        a = _find(_compare(), "Saturn", "Neptune")
        assert a["aspect"] == "opposition"
        assert a["applying"] is False
        assert a["days_to_exact"] == pytest.approx(-28.0, abs=0.5)

    def test_jupiter_square_natal_ascendant_is_separating(self):
        result = _compare(include_angles="natal")
        a = _find(result, "Ascendant", "Jupiter")
        assert a["aspect"] == "square"
        assert a["orb"] == pytest.approx(2.46, abs=0.01)
        assert a["applying"] is False

    def test_exact_utc_is_none_without_reference_metadata(self):
        transit = {k: v for k, v in TRANSIT.items() if k != "metadata"}
        result = compare_charts(
            NATAL, transit, orb_multiplier=0.6,
            chart1_meta=NATAL_META, chart2_meta=TRANSIT_META,
        )
        a = _find(result, "Neptune", "Mars")
        assert a["applying"] is False
        assert a["exact_utc"] is None

    def test_natal_only_comparison_has_no_direction(self):
        result = compare_charts(NATAL, NATAL, orb_multiplier=0.6)
        assert result["aspects"], "expected some natal-natal aspects"
        assert all(a["applying"] is None for a in result["aspects"])
        assert all(a["days_to_exact"] is None for a in result["aspects"])
        assert all(a["exact_utc"] is None for a in result["aspects"])


# ---------------------------------------------------------------------------
# compare_charts: include_angles and the planets_only alias
# ---------------------------------------------------------------------------

def _mini(n_planets, with_point):
    planets = {f"P{i}": {"degree": 10.0 + i, "sign": "Aries"} for i in range(n_planets)}
    points = {"Ascendant": {"degree": 20.0, "sign": "Aries"}} if with_point else {}
    return {"planets": planets, "points": points}


class TestIncludeAngles:
    """A huge orb multiplier makes every body pair an aspect, so counts are n1 * n2."""

    def _count(self, **kwargs):
        result = compare_charts(
            _mini(2, True), _mini(2, True), orb_multiplier=100,
            chart1_meta=NATAL_META, chart2_meta=TRANSIT_META, **kwargs,
        )
        return result["metadata"]["total_aspects"]

    def test_default_is_planets_only(self):
        assert self._count() == 4

    def test_none(self):
        assert self._count(include_angles="none") == 4

    def test_natal_adds_only_chart1_angles(self):
        assert self._count(include_angles="natal") == 6

    def test_transit_adds_only_chart2_angles(self):
        assert self._count(include_angles="transit") == 6

    def test_both_adds_all_angles(self):
        assert self._count(include_angles="both") == 9

    def test_planets_only_true_maps_to_none(self):
        assert self._count(planets_only=True) == 4

    def test_planets_only_false_maps_to_both(self):
        assert self._count(planets_only=False) == 9

    def test_include_angles_wins_over_planets_only(self):
        assert self._count(planets_only=True, include_angles="natal") == 6
        assert self._count(planets_only=False, include_angles="none") == 4

    def test_natal_with_no_natal_chart_includes_no_angles(self):
        result = compare_charts(
            _mini(2, True), _mini(2, True), orb_multiplier=100,
            chart1_meta=TRANSIT_META, chart2_meta=TRANSIT_META, include_angles="natal",
        )
        assert result["metadata"]["total_aspects"] == 4

    def test_natal_angles_only_from_natal_chart(self):
        result = _compare(include_angles="natal")
        angle_hits = [a for a in result["aspects"] if "Ascendant" in (a["body1"], a["body2"]) or "MC" in (a["body1"], a["body2"])]
        assert angle_hits, "expected natal angle aspects"
        assert all(a["body1"] in ("Ascendant", "MC") for a in angle_hits)
        assert all(a["body1_chart"] == "natal" for a in angle_hits)

    def test_invalid_include_angles_raises(self):
        with pytest.raises(AnalysisError):
            _compare(include_angles="sideways")

    def test_metadata_reports_effective_mode(self):
        assert _compare(include_angles="natal")["metadata"]["include_angles"] == "natal"
        assert _compare()["metadata"]["include_angles"] == "none"
        assert _compare(planets_only=False)["metadata"]["include_angles"] == "both"


# ---------------------------------------------------------------------------
# compare_charts: backward-compatible result shape and labels
# ---------------------------------------------------------------------------

class TestResultShape:
    def test_original_keys_are_still_present(self):
        result = _compare()
        a = result["aspects"][0]
        for key in ("body1", "body1_position", "body2", "body2_position", "aspect",
                    "exact_angle", "actual_angle", "orb", "orb_used"):
            assert key in a
        meta = result["metadata"]
        for key in ("chart1_date", "chart2_date", "orb_multiplier", "planets_only", "total_aspects"):
            assert key in meta

    def test_bodies_carry_chart_labels(self):
        a = _find(_compare(), "Neptune", "Mars")
        assert a["body1_chart"] == "natal"
        assert a["body2_chart"] == "transit"

    def test_metadata_describes_both_charts(self):
        meta = _compare()["metadata"]
        assert meta["chart1"]["kind"] == "natal"
        assert meta["chart1"]["date"] == "1981-05-06"
        assert meta["chart2"]["kind"] == "transit"
        assert meta["chart2"]["date"] == "2026-09-19"
        assert meta["chart2"]["time"] == "09:00:00"

    def test_old_call_style_still_works(self):
        result = compare_charts(NATAL, TRANSIT)
        assert result["aspects"]
        assert result["metadata"]["planets_only"] is True


# ---------------------------------------------------------------------------
# Text formatter
# ---------------------------------------------------------------------------

class TestTextFormat:
    def test_original_lines_are_unchanged_and_one_line_is_appended(self):
        text = format_aspect_report(_compare())
        assert (
            "**Neptune** Quincunx **Mars**\n"
            "  Neptune: 24.45° Sagittarius\n"
            "  Mars: 24.79° Cancer\n"
            "  Orb: 0.34°\n"
            "  Neptune = natal · Mars = transit · separating · exact ~0.6 days ago (≈ 2026-09-18 19:24 UT)\n"
            "\n"
        ) in text

    def test_header_lines_are_unchanged(self):
        text = format_aspect_report(_compare())
        assert text.startswith(
            "# Aspect Analysis\n\n"
            "Chart 1: 1981-05-06\n"
            "Chart 2: 2026-09-19\n"
        )
        assert "Orb Multiplier: 0.6\n\n## Aspects (sorted by tightness)\n\n" in text

    def test_applying_line(self):
        text = format_aspect_report(_compare())
        assert (
            "  Mercury = natal · Mars = transit · applying · exact in ~0.6 days (≈ 2026-09-19 23:48 UT)\n"
        ) in text

    def test_multi_day_estimate(self):
        text = format_aspect_report(_compare())
        assert "applying · exact in ~7.6 days (≈ 2026-09-27 00:00 UT)" in text

    def test_no_direction_means_no_motion_words(self):
        c1 = {"planets": {"Sun": {"degree": 10.0, "sign": "Aries"}}}
        c2 = {"planets": {"Moon": {"degree": 12.0, "sign": "Aries"}}}
        text = format_aspect_report(compare_charts(c1, c2))
        assert "  Sun = chart 1 · Moon = chart 2\n" in text
        assert "applying" not in text and "separating" not in text and "exact" not in text

    def test_exact_now(self):
        c1 = {"planets": {"Sun": {"degree": 10.0, "sign": "Aries"}}}
        c2 = {"planets": {"Moon": {"degree": 10.0, "sign": "Aries", "speed": 1.0}}}
        text = format_aspect_report(compare_charts(c1, c2))
        assert "  Sun = chart 1 · Moon = chart 2 · exact now\n" in text

    def test_sub_tenth_of_a_day_is_not_shown_as_zero(self):
        c1 = {"planets": {"Sun": {"degree": 10.0, "sign": "Aries"}}}
        applying = {"planets": {"Moon": {"degree": 9.97, "sign": "Aries", "speed": 1.0}}}
        separating = {"planets": {"Moon": {"degree": 10.03, "sign": "Aries", "speed": 1.0}}}
        assert "applying · exact in <0.1 days\n" in format_aspect_report(compare_charts(c1, applying))
        assert "separating · exact <0.1 days ago\n" in format_aspect_report(compare_charts(c1, separating))

    def test_synastry_line_uses_names(self):
        result = compare_charts(
            NATAL, NATAL, orb_multiplier=0.6,
            chart1_meta={"kind": "natal", "name": "Todd"},
            chart2_meta={"kind": "natal", "name": "Liz"},
        )
        text = format_aspect_report(result)
        assert "= natal (Todd) · " in text and "= natal (Liz)\n" in text

    def test_no_aspects_message_is_unchanged(self):
        c1 = {"planets": {"Sun": {"degree": 10.0, "sign": "Aries"}}}
        c2 = {"planets": {"Moon": {"degree": 10.0, "sign": "Taurus"}}}  # 30 deg -> semi-sextile 2 deg orb
        far = {"planets": {"Moon": {"degree": 20.0, "sign": "Taurus"}}}  # 40 deg: no aspect
        assert "No aspects found within orb limits." in format_aspect_report(compare_charts(c1, far))
        assert "No aspects found" not in format_aspect_report(compare_charts(c1, c2))


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

class TestJsonFormat:
    def test_is_valid_json_with_expected_top_level_keys(self):
        payload = json.loads(format_aspect_json(_compare()))
        assert set(payload) == {"metadata", "aspects"}

    def test_metadata_shape(self):
        meta = json.loads(format_aspect_json(_compare(include_angles="natal")))["metadata"]
        assert meta["chart1"] == {
            "kind": "natal", "label": "natal", "name": None,
            "date": "1981-05-06", "time": "00:50:00",
        }
        assert meta["chart2"]["kind"] == "transit"
        assert meta["chart2"]["time"] == "09:00:00"
        assert meta["orb_multiplier"] == 0.6
        assert meta["include_angles"] == "natal"
        assert meta["total_aspects"] == len(json.loads(format_aspect_json(_compare(include_angles="natal")))["aspects"])

    def test_aspect_shape_and_types(self):
        payload = json.loads(format_aspect_json(_compare()))
        a = next(x for x in payload["aspects"]
                 if x["body1"]["name"] == "Neptune" and x["body2"]["name"] == "Mars")
        assert a["aspect"] == "quincunx"
        assert a["exact_angle"] == 150
        assert isinstance(a["orb"], float) and isinstance(a["orb_used"], float)
        assert a["applying"] is False
        assert isinstance(a["days_to_exact"], float)
        assert a["exact_utc"] == "2026-09-18T19:24:00Z"
        assert a["body1"] == {
            "name": "Neptune", "chart": "natal", "chart_index": 1,
            "sign": "Sagittarius", "degree": 24.45,
            "absolute": pytest.approx(264.45), "speed": None,
        }
        assert a["body2"]["chart"] == "transit"
        assert a["body2"]["chart_index"] == 2
        assert a["body2"]["speed"] == pytest.approx(0.6)

    def test_nulls_when_direction_unknown(self):
        payload = json.loads(format_aspect_json(compare_charts(NATAL, NATAL, orb_multiplier=0.6)))
        first = payload["aspects"][0]
        assert first["applying"] is None
        assert first["days_to_exact"] is None
        assert first["exact_utc"] is None

    def test_no_display_strings_in_data(self):
        text = format_aspect_json(_compare())
        assert "↗" not in text and "↘" not in text and "[[" not in text


# ---------------------------------------------------------------------------
# handle_compare_charts (extracted handler)
# ---------------------------------------------------------------------------

from w8s_astro_mcp.server import handle_compare_charts  # noqa: E402


def _patches(natal=NATAL, transit=TRANSIT, db=None):
    import w8s_astro_mcp.server as srv
    return (
        patch.object(srv, "get_natal_chart_data", return_value=natal),
        patch.object(srv, "get_chart_for_date", return_value=transit),
        patch.object(srv, "init_db", return_value=db or MagicMock()),
    )


@pytest.mark.asyncio
async def test_handler_defaults_keep_original_text_layout():
    pn, pt, pd = _patches()
    with pn, pt, pd:
        result = await handle_compare_charts({"chart1_date": "natal", "chart2_date": "today"})
    text = result[0].text
    assert text.startswith("# Aspect Analysis\n\nChart 1: 1981-05-06\nChart 2: 2026-09-19\n")
    assert "Total Aspects Found:" in text
    assert "Neptune = natal · Mars = transit" in text
    assert "Ascendant" not in text  # angles are off by default


@pytest.mark.asyncio
async def test_handler_json_format():
    pn, pt, pd = _patches()
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart2_date": "today", "format": "json", "orb_multiplier": 0.6}
        )
    payload = json.loads(result[0].text)
    assert payload["metadata"]["chart1"]["kind"] == "natal"
    assert payload["metadata"]["chart2"]["kind"] == "transit"
    assert payload["metadata"]["include_angles"] == "none"


@pytest.mark.asyncio
async def test_handler_include_angles_natal_uses_only_natal_angles():
    pn, pt, pd = _patches()
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart2_date": "today", "format": "json",
             "orb_multiplier": 0.6, "include_angles": "natal"}
        )
    aspects = json.loads(result[0].text)["aspects"]
    angle_bodies = [
        b for a in aspects for b in (a["body1"], a["body2"]) if b["name"] in ("Ascendant", "MC")
    ]
    assert angle_bodies, "expected natal angle aspects"
    assert all(b["chart_index"] == 1 for b in angle_bodies)


@pytest.mark.asyncio
async def test_handler_planets_only_false_still_means_both_charts_angles():
    pn, pt, pd = _patches()
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart2_date": "today", "format": "json",
             "orb_multiplier": 0.6, "planets_only": False}
        )
    payload = json.loads(result[0].text)
    assert payload["metadata"]["include_angles"] == "both"
    indexes = {
        b["chart_index"] for a in payload["aspects"] for b in (a["body1"], a["body2"])
        if b["name"] in ("Ascendant", "MC")
    }
    assert indexes == {1, 2}


@pytest.mark.asyncio
async def test_handler_invalid_format_is_a_clear_error():
    pn, pt, pd = _patches()
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart2_date": "today", "format": "yaml"}
        )
    assert result[0].text.startswith("Error:")
    assert "format" in result[0].text


@pytest.mark.asyncio
async def test_handler_invalid_include_angles_is_a_clear_error():
    pn, pt, pd = _patches()
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart2_date": "today", "include_angles": "sideways"}
        )
    assert result[0].text.startswith("Error:")
    assert "include_angles" in result[0].text


@pytest.mark.asyncio
async def test_handler_unknown_event_label():
    db = MagicMock()
    db.get_event_chart_by_label.return_value = None
    pn, pt, pd = _patches(db=db)
    with pn, pt, pd:
        result = await handle_compare_charts({"chart1_date": "natal", "chart2_date": "event:nope"})
    assert "no saved event chart with label 'nope'" in result[0].text


@pytest.mark.asyncio
async def test_handler_event_chart_gets_event_label_and_no_direction():
    db = MagicMock()
    db.get_event_chart_by_label.return_value = SimpleNamespace(id=7)
    event_chart = {
        "planets": {"Mars": {"degree": 24.79, "sign": "Cancer"}},  # DB charts carry no speed
        "points": {},
        "metadata": {"date": "2026-09-19", "time": "09:00:00"},
    }
    db.get_event_chart_positions.return_value = event_chart
    pn, pt, pd = _patches(db=db)
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart2_date": "event:full-moon", "orb_multiplier": 0.6}
        )
    text = result[0].text
    assert "Neptune = natal · Mars = event:full-moon\n" in text
    assert "applying" not in text and "separating" not in text


@pytest.mark.asyncio
async def test_handler_synastry_labels_use_profile_names():
    db = MagicMock()
    db.get_profile_by_id.side_effect = lambda pid: SimpleNamespace(name={1: "Todd", 3: "Liz"}[pid])
    pn, pt, pd = _patches(db=db)
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart1_profile_id": 1,
             "chart2_date": "natal", "chart2_profile_id": 3, "orb_multiplier": 0.6}
        )
    text = result[0].text
    assert "= natal (Todd) · " in text
    assert "= natal (Liz)\n" in text


@pytest.mark.asyncio
async def test_handler_synastry_without_resolvable_names_uses_chart_numbers():
    pn, pt, pd = _patches()  # db is a bare MagicMock: names are not strings
    with pn, pt, pd:
        result = await handle_compare_charts(
            {"chart1_date": "natal", "chart2_date": "natal", "orb_multiplier": 0.6}
        )
    text = result[0].text
    assert "= natal, chart 1 · " in text
    assert "= natal, chart 2\n" in text
