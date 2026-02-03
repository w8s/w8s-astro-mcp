# w8s-astro-mcp Development Roadmap

## Phase 1: MVP ✅ (In Progress)
- [x] Project structure created
- [ ] Parse swetest output
- [ ] JSON cache (7-day rolling)
- [ ] Basic transit data structure
- [ ] Detect mechanical changes (degrees, sign changes, stelliums)
- [ ] Rich JSON return format
- [ ] Setup wizard for birth data config
- [ ] Generate markdown tables

## Phase 2: Smart Analysis
- [ ] Retrograde station detection
- [ ] Daily motion calculations
- [ ] Speed anomaly detection (unusually slow/fast)
- [ ] Named locations system
- [ ] Location switching (`get_transits(location="work")`)

## Phase 3: Aspect Engine
- [ ] Calculate major aspects (conjunction, opposition, square, trine, sextile)
- [ ] Configurable orbs
- [ ] Applying vs separating
- [ ] Aspect patterns (T-squares, Grand Trines, etc.)

## Phase 4: Historical & Predictive
- [ ] SQLite migration for long-term storage
- [ ] Query historical transits
- [ ] "When was the last time...?" queries
- [ ] Future transit lookups ("Next Mercury retrograde?")
- [ ] Transit-to-natal aspects

## Phase 5: Location Intelligence 🎯
- [ ] **Device location detection** (CoreLocationCLI integration)
- [ ] Opt-in auto-detection config
- [ ] Compare to saved locations ("You're at home" vs "You're traveling")
- [ ] Travel mode (temporary location override)
- [ ] Location history log
- [ ] "Ask me when location changes" prompt

## Phase 6: Integration
- [ ] Combine with tarot workflow
- [ ] Calendar integration (transit alerts for important meetings)
- [ ] Obsidian daily note auto-insertion
- [ ] Custom alert thresholds

## Future/Maybe
- [ ] Progressions & Solar Returns
- [ ] Synastry (relationship charts)
- [ ] Electional astrology helpers
- [ ] Voice mode integration ("What's my transit weather?")
