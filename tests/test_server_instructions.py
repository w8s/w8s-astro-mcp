"""The server sends short, durable guidance to the AI in the MCP initialize response.

This is where the rules that never change live (which times are local and which are UT, and how to
treat a data notice). Facts that change with the user's data live in tool results instead.
"""

import w8s_astro_mcp.server as srv


def _instructions() -> str:
    return srv.app.create_initialization_options().instructions


def test_instructions_are_sent_on_initialize():
    assert _instructions()


def test_instructions_explain_local_versus_ut_times():
    text = _instructions()
    assert "UT" in text
    for tool in ("get_transits", "find_house_placements", "compare_charts"):
        assert tool in text
    assert "local" in text
    assert "birth time" in text and "cast_event_chart" in text


def test_instructions_say_how_to_treat_a_data_notice():
    text = _instructions().lower()
    assert "data notice" in text
    assert "consent" in text
    assert "tell the user" in text


def test_instructions_stay_short():
    assert len(_instructions()) < 1500      # guidance, not documentation
