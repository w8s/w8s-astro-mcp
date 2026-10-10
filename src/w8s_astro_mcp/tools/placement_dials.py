"""
Placement dials: an interactive page for learning what a planet, a sign and a house
mean, alone and together.

The tool writes one self-contained HTML file. Three dials (planet, sign, house) can be
turned or switched off, and a reading is composed from whichever layers are on. The
chart's own placements and house cusps are loaded as quick picks.

The page is a string.Template (templates/placement_dials.html) with two slots:
  $content_json  the meaning text, from templates/placement_dials_content.json
  $chart_json    this chart's cusps and planet placements, built here

Houses are worked out from the cusps instead of read from stored house numbers, so
a chart that was recalculated (or not yet) always agrees with its own cusps.
"""

import json
from importlib import resources
from pathlib import Path
from string import Template
from typing import Any, Dict, List

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
PLANET_ORDER = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

DEFAULT_OUTPUT_PATH = "~/Downloads/placement_dials.html"
DEFAULT_TITLE = "Natal placements"

_PACKAGE = "w8s_astro_mcp"


class PlacementDialsError(ValueError):
    """The chart data could not be turned into a placement dials page."""


def absolute_position(sign: str, degree: float) -> float:
    """Sign plus degree within the sign, as a position on the 0-360 wheel."""
    try:
        return SIGN_NAMES.index(sign) * 30 + float(degree)
    except ValueError as e:
        raise PlacementDialsError(f"Unknown sign: {sign!r}") from e


def house_of(position: float, cusps: List[float]) -> int:
    """
    House (1-12) that holds a position, given the 12 house cusps as absolute positions.

    Handles houses that cross 0 degrees Aries. A house runs from its cusp up to,
    but not including, the next cusp.
    """
    for i in range(12):
        start = cusps[i]
        width = (cusps[(i + 1) % 12] - start) % 360
        if (position - start) % 360 < width:
            return i + 1
    raise PlacementDialsError(f"Position {position} does not fall in any house; check the house cusps.")


def build_chart_data(chart: Dict[str, Any], title: str = DEFAULT_TITLE) -> Dict[str, Any]:
    """
    Reduce natal chart data to what the page needs.

    Args:
        chart: the dict from get_natal_chart_data (planets, houses, points)
        title: heading shown above the placement quick picks

    Returns:
        {"title": str,
         "cusps": [sign index for houses 1..12],
         "placements": [[planet index, sign index, house number], ...]}
        Indexes are positions in the content file's planets and signs lists.
    """
    houses = chart.get("houses") or {}
    missing = [n for n in range(1, 13) if str(n) not in houses]
    if missing:
        raise PlacementDialsError(
            "This chart has no house cusps for house(s) " + ", ".join(map(str, missing)) + "."
        )

    cusp_positions = [
        absolute_position(houses[str(n)]["sign"], houses[str(n)]["degree"]) for n in range(1, 13)
    ]
    cusp_signs = [SIGN_NAMES.index(houses[str(n)]["sign"]) for n in range(1, 13)]

    planets = chart.get("planets") or {}
    placements = []
    for index, name in enumerate(PLANET_ORDER):
        if name not in planets:
            continue
        sign = planets[name]["sign"]
        position = absolute_position(sign, planets[name]["degree"])
        placements.append([index, SIGN_NAMES.index(sign), house_of(position, cusp_positions)])

    if not placements:
        raise PlacementDialsError("This chart has no planet positions.")

    return {"title": title, "cusps": cusp_signs, "placements": placements}


def _json_for_script(value: Any) -> str:
    """JSON that is safe to place inside an inline <script> element."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _read_resource(name: str) -> str:
    return resources.files(_PACKAGE).joinpath("templates", name).read_text(encoding="utf-8")


def load_content() -> Dict[str, Any]:
    """The meaning text for planets, signs and houses (templates/placement_dials_content.json)."""
    return json.loads(_read_resource("placement_dials_content.json"))


def render_placement_dials(chart: Dict[str, Any], title: str = DEFAULT_TITLE) -> str:
    """Return the finished HTML page for a chart."""
    template = Template(_read_resource("placement_dials.html"))
    return template.substitute(
        content_json=_json_for_script(load_content()),
        chart_json=_json_for_script(build_chart_data(chart, title)),
    )


def resolve_output_path(output_path: str = DEFAULT_OUTPUT_PATH) -> Path:
    """
    Expand the requested path. A folder (an existing directory, or a path ending in a
    separator) gets the default file name inside it.
    """
    raw = output_path or DEFAULT_OUTPUT_PATH
    path = Path(raw).expanduser()
    if path.is_dir() or raw.endswith(("/", "\\")):
        path = path / Path(DEFAULT_OUTPUT_PATH).name
    return path.resolve()


def create_placement_dials(
    chart: Dict[str, Any],
    title: str = DEFAULT_TITLE,
    output_path: str = DEFAULT_OUTPUT_PATH,
) -> str:
    """Write the page to disk (creating folders as needed) and return the saved path."""
    html = render_placement_dials(chart, title)
    path = resolve_output_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)
