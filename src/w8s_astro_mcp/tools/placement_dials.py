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
import tempfile
import re
import sys
import unicodedata
import webbrowser
from importlib import resources
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Sequence

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
CONTENT_OVERRIDE_PATH = "~/.w8s-astro-mcp/placement_dials_content.json"


class PlacementDialsError(ValueError):
    """The chart data could not be turned into a placement dials page."""


def absolute_position(sign: Any, degree: Any, label: str = "A position") -> float:
    """Sign plus degree within the sign, as a position on the 0-360 wheel."""
    if sign not in SIGN_NAMES:
        raise PlacementDialsError(f"{label} has an unknown sign: {sign!r}.")
    try:
        deg = float(degree)
    except (TypeError, ValueError) as e:
        raise PlacementDialsError(f"{label} has no usable degree (got {degree!r}).") from e
    if not 0 <= deg < 30:
        raise PlacementDialsError(f"{label} has a degree outside its sign (got {deg}).")
    return SIGN_NAMES.index(sign) * 30 + deg


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


def build_chart_data(
    chart: Dict[str, Any],
    title: str = DEFAULT_TITLE,
    notices: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Reduce natal chart data to what the page needs.

    Args:
        chart: the dict from get_natal_chart_data (planets, houses, points)
        title: heading shown above the placement quick picks
        notices: short caveats to show under the quick picks (for example an
            uncertain birth time)

    Returns:
        {"title": str,
         "notices": [str, ...],
         "cusps": [sign index for houses 1..12],
         "placements": [[planet index, sign index, house number], ...]}
        Indexes are positions in the content file's planets and signs lists.
    """
    houses = chart.get("houses") or {}
    missing = [n for n in range(1, 13) if not isinstance(houses.get(str(n)), dict)]
    if missing:
        raise PlacementDialsError(
            "This chart has no house cusps for house(s) " + ", ".join(map(str, missing))
            + ". Cusps cannot always be calculated (very high latitudes, or no birth location), "
            "so check the profile's birth location and time."
        )

    cusp_positions = [
        absolute_position(houses[str(n)].get("sign"), houses[str(n)].get("degree"), f"House {n} cusp")
        for n in range(1, 13)
    ]
    cusp_signs = [int(pos // 30) for pos in cusp_positions]

    planets = chart.get("planets") or {}
    placements = []
    for index, name in enumerate(PLANET_ORDER):
        if name not in planets:
            continue
        entry = planets[name] or {}
        position = absolute_position(entry.get("sign"), entry.get("degree"), name)
        placements.append([index, int(position // 30), house_of(position, cusp_positions)])

    if not placements:
        raise PlacementDialsError("This chart has no planet positions.")

    return {"title": title, "notices": list(notices or []), "cusps": cusp_signs, "placements": placements}


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


def validate_content(c: Dict[str, Any]) -> None:
    """Raise PlacementDialsError if the meaning text is missing something the page needs."""
    def need(ok: bool, what: str) -> None:
        if not ok:
            raise PlacementDialsError(f"Placement dials content problem: {what}.")

    need(isinstance(c.get("planets"), list) and [p.get("name") for p in c["planets"]] == PLANET_ORDER,
         "'planets' must list " + ", ".join(PLANET_ORDER) + " in that order")
    for p in c["planets"]:
        need(all(p.get(k) for k in ("glyph", "does", "core", "keywords")),
             f"planet {p.get('name')} needs glyph, does, core and keywords")
    need(isinstance(c.get("signs"), list) and [x.get("name") for x in c["signs"]] == SIGN_NAMES,
         "'signs' must list the twelve signs from Aries to Pisces in order")
    elements = set(c.get("element_text") or {})
    modes = set(c.get("mode_text") or {})
    need(elements == {"fire", "earth", "air", "water"}, "'element_text' needs fire, earth, air and water")
    for x in c["signs"]:
        need(x.get("manner") and x.get("element") in elements and x.get("mode") in modes,
             f"sign {x.get('name')} needs manner, a known element and a known mode")
    for key, count in (("houses", 12), ("rulers", 12), ("rulers_traditional", 12), ("angularity", 3)):
        need(isinstance(c.get(key), list) and len(c[key]) == count, f"'{key}' needs exactly {count} entries")
    need(all(c["houses"]), "every house needs text")
    for key in ("rulers", "rulers_traditional"):
        need(set(c[key]) <= set(PLANET_ORDER), f"'{key}' may only name the ten planets")
    need(isinstance(c.get("dignity"), dict) and list(c["dignity"]) == PLANET_ORDER,
         "'dignity' needs the ten planets in order")
    for name, d in c["dignity"].items():
        need(all(isinstance(d.get(k), list) for k in ("domicile", "exaltation", "detriment", "fall")),
             f"dignity for {name} needs domicile, exaltation, detriment and fall lists")
    need(isinstance(c.get("mode_text"), dict) and modes >= {x["mode"] for x in c["signs"]},
         "'mode_text' needs every mode the signs use")


def content_override_path() -> Path:
    return Path(CONTENT_OVERRIDE_PATH).expanduser()


def load_content() -> Dict[str, Any]:
    """
    The meaning text for planets, signs and houses.

    Comes from templates/placement_dials_content.json inside the package. To keep your
    own wording through upgrades, put a file at ~/.w8s-astro-mcp/placement_dials_content.json
    holding only the keys you want to change (for example just "houses"). Its keys replace
    the packaged ones, and the result is checked before the page is built.
    """
    content = json.loads(_read_resource("placement_dials_content.json"))
    override = content_override_path()
    if override.is_file():
        try:
            mine = json.loads(override.read_text(encoding="utf-8"))
            if not isinstance(mine, dict):
                raise ValueError("the top level must be a JSON object")
        except (OSError, ValueError) as e:
            raise PlacementDialsError(
                f"Could not read your content file {override}: {e}. Fix it or move it aside."
            ) from e
        content.update(mine)
        try:
            validate_content(content)
        except PlacementDialsError as e:
            raise PlacementDialsError(f"{e} (from your content file {override}; fix it or move it aside)") from e
    return content


def render_placement_dials(
    chart: Dict[str, Any],
    title: str = DEFAULT_TITLE,
    notices: Optional[Sequence[str]] = None,
) -> str:
    """Return the finished HTML page for a chart."""
    template = Template(_read_resource("placement_dials.html"))
    return template.substitute(
        content_json=_json_for_script(load_content()),
        chart_json=_json_for_script(build_chart_data(chart, title, notices)),
    )


def slugify(text: str) -> str:
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
    label = slugify(profile_name or "") or (f"profile{int(profile_id)}" if profile_id is not None else "")
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
    notices: Optional[Sequence[str]] = None,
) -> str:
    """
    Write the page to disk (creating folders as needed) and return the saved path.

    The page is written to a temporary file beside the target and then moved into place,
    so an interrupted write never leaves a half page behind.
    """
    path = resolve_output_path(output_path, profile_name, profile_id)
    html = render_placement_dials(chart, title, notices)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
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
