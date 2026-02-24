# Design Decisions

This document records intentional design choices that may seem like limitations,
along with the reasoning and the path to changing them if needed.

---

## `get_ingresses` — Extended Mode Omits Inner Planets

**Decision:** When `extended=True`, only outer planets (Jupiter, Saturn, Uranus,
Neptune, Pluto) are returned. Inner planets (Sun, Moon, Mercury, Venus, Mars)
are excluded.

**Why:** Inner planets move fast. Over a multi-year window:
- The Moon changes signs every ~2.5 days → ~146 events/year
- Mercury changes signs every ~2-4 weeks → ~15-20 events/year
- The Sun changes signs monthly → ~12 events/year

A 10-year extended scan would produce 1,500+ Moon events alone. The output
becomes noise rather than signal, and the primary use case for extended mode
is historical or far-future context where outer planet cycles are what matter
(e.g. "what were the major planetary alignments during the Renaissance?",
"when does Pluto enter Aquarius?", "what was the outer planet weather during
the life of Jesus?").

**If you disagree or have a use case that needs inner planets over long windows:**

Open an issue. The right solution is probably one of:
1. A `planets` filter parameter on `get_ingresses` (e.g. `planets=["Sun", "Mercury"]`)
2. A separate `get_inner_planet_ingresses` tool with its own output format
   designed for high-volume results (e.g. paginated, or returning a summary
   table rather than a narrative list)

The current constraint exists to keep output readable for the primary user
(an AI assistant), not as a permanent architectural limitation.

---

## `get_ingresses` — Offset and Days Caps

**Normal mode caps:**
- `offset`: 0–36,500 days (~100 years from today)
- `days`: 1–365

**Extended mode caps:**
- `offset`: uncapped (Swiss Ephemeris supports 13,000 BCE – 17,000 CE)
- `days`: 1–3,650 (~10 years)

**Why the 10-year scan cap in extended mode:** Even with outer planets only,
a 100-year scan returns ~40 Pluto events, ~120 Neptune events, ~240 Uranus
events, ~480 Saturn events, ~960 Jupiter events — over 1,800 events total.
The 10-year cap keeps results in a useful range (~180 events max) while still
covering most research questions. If you need longer, call the tool multiple
times with different offsets.

**Note:** The 36,500-day offset cap in normal mode (~100 years) is generous
enough for retirement planning, generational forecasting, and most practical
predictive astrology. The ephemeris itself imposes no meaningful limit.
