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
import os
import re
import sys
import unicodedata
import webbrowser
from importlib import resources
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
PLANET_ORDER = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

DEFAULT_OUTPUT_PATH = "~/Downloads/placement_dials.html"
DEFAULT_FILE_NAME = "placement_dials.html"
ALLOWED_SUFFIXES = (".html", ".htm")
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
    """
    JSON that is safe to place inside an inline <script> element.

    Every "<", ">" and "&" is written as a unicode escape. That is still the same JSON
    string to the script, but the HTML parser never sees "</script>" or "<!--<script>"
    inside the data, either of which can end the script early.
    """
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


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


def _slug(text: str) -> str:
    """Lowercase letters and digits only, words joined by underscores ("Liz W." -> "liz_w")."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")[:40]


def default_file_name(profile_name: Optional[str] = None, profile_id: Optional[int] = None) -> str:
    """
    File name used when none is given: placement_dials_<profile name>.html, so each
    person's page keeps its own file. A name with nothing usable in it falls back to the
    profile id, and with neither the plain default name is used.
    """
    stem, suffix = DEFAULT_FILE_NAME.rsplit(".", 1)
    label = _slug(profile_name or "") or (f"profile{int(profile_id)}" if profile_id is not None else "")
    return f"{stem}_{label}.{suffix}" if label else DEFAULT_FILE_NAME


def resolve_output_path(
    output_path: Optional[str] = None,
    profile_name: Optional[str] = None,
    profile_id: Optional[int] = None,
) -> Path:
    """
    Expand the requested path. A folder (an existing directory, or a path ending in a
    separator) gets the default file name inside it. With no path at all the file goes
    to ~/Downloads.

    Only .html and .htm files are written, so a wrong path (a dotfile, a script, a note)
    can never be overwritten with a web page.
    """
    name = default_file_name(profile_name, profile_id)
    raw = output_path or str(Path(DEFAULT_OUTPUT_PATH).with_name(name))
    path = Path(raw).expanduser()
    if path.is_dir() or raw.endswith(("/", "\\")):
        path = path / name
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise PlacementDialsError(
            f"Output file must end in .html or .htm (got {path.name!r}). "
            "Give a file name like placement_dials.html, or a folder."
        )
    return path.resolve()


def create_placement_dials(
    chart: Dict[str, Any],
    title: str = DEFAULT_TITLE,
    output_path: Optional[str] = None,
    profile_name: Optional[str] = None,
    profile_id: Optional[int] = None,
) -> str:
    """Write the page to disk (creating folders as needed) and return the saved path."""
    path = resolve_output_path(output_path, profile_name, profile_id)
    html = render_placement_dials(chart, title)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


def open_in_default_browser(path: str) -> bool:
    """
    Open a saved page in the default browser.

    Returns whether a browser took the request. It never raises: on a machine with no
    desktop session the answer is simply False, and the caller says so. On Linux with no
    display it does not try at all: Python would fall back to a console browser that
    blocks this server and shares its input and output.
    """
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        return False
    try:
        return bool(webbrowser.open(Path(path).resolve().as_uri()))
    except Exception:
        return False
