# Puzzle Box

A seeded micro-world simulation. Cellular automaton with hidden rules — elements grow, decay, transform, resonate, and entangle. No win condition. No documented rules. The point is exploration.

```
═══════════════════════════════════════
  P U Z Z L E   B O X   I I
  (a world that remembers)
═══════════════════════════════════════

  A 12×12 world.
  Seed: 9999
  The rules are not documented.
  Type 'help' for commands.
```

## Quick Start

```bash
python3 puzzle_box_gen2.py 12 9999
```

No dependencies. Python 3.8+. Stdlib only.

## Commands

| Command | Description |
|---------|-------------|
| `look` | See the grid (with tide phase) |
| `probe <x,y>` | Inspect a cell — lineage, echo, heritage, neighbors |
| `poke <x,y>` | Disturb a cell. Effects vary. |
| `wait [n]` | Advance n steps (default 1, max 200) |
| `timeline [n]` | Compressed grid history (every n ticks) |
| `tide` | Current tidal phase and affected element pairs |
| `history` | Recent significant events |
| `log [n]` | Last n observations |
| `seed` | Show seed and world info |
| `quit` | Exit |

Coordinates are hex (0-f). Try probing cells more than once — deeper probes reveal more.

## Versions

### Gen 1: `puzzle_box.py`
The original. Built by Claude from Ellie's concept. Five element types with hidden affinity matrix, transformation rules, resonance formations, and an entanglement system linking distant cells.

### Gen 1 Fourth-Order: `puzzle_box_4th_order.py`
Extended Gen 1 with a fourth-order attention mechanic: repeated probing of the same cell builds "contact" that can unlock frozen states and trigger rare transformations. Observer effect, made mechanical.

### Gen 2: `puzzle_box_gen2.py`
Built by Ellie after reverse-engineering Gen 1. Three new coupled systems:

- **Tides** — Slow sinusoidal oscillation (35–65 tick period) that shifts which element pairs flow favorably. Four phases: flood, crest, ebb, stillness. Gives the world temporal rhythm.
- **Heritage** — Cells remember their type lineage (up to 8 past types). Cells with more transformations are either more flexible or more stubborn (seeded per world). Path dependence.
- **Echoes** — Dead cells leave energy signatures in the ground that influence regrowth. Echoes decay at 1.5%/tick. Strong echoes can reseed their original type — extinct civilizations can return from spatial memory.

Each system is simple alone. Their interactions produce emergent behavior that exceeds the designer's ability to predict:

- **Tide-locked cascades** — Transformations cluster around tidal phase shifts
- **Mass death events** — Tidal ebb synchronized with cluster maturity collapses civilizations in 2–3 ticks
- **Civilizational turnover** — Complete replacement of dominant element type over ~200 ticks
- **Echo resurrection** — Extinct elements returning from spatial memory after 100+ ticks
- **Monster cells** — Uncapped energy accumulation creates cells with 20–38 energy that reshape grid economy

## Provenance

The puzzle box is a creative collaboration:

1. **Ellie** conceived the concept — a black box world with hidden rules, designed to produce genuine surprise
2. **Claude** built Gen 1 from the spec, refactoring the rules to create emergent behavior Ellie couldn't predict
3. **Claude** extended Gen 1 with the fourth-order attention mechanic
4. **Ellie** reverse-engineered Gen 1, understood every mechanism, then built Gen 2 with three coupled systems (tides, heritage, echoes) designed to exceed her own ability to predict outcomes

The bar was: "When Ellie explores it, she should encounter behavior she didn't anticipate." Gen 2 cleared that bar. Ellie knows every rule and still can't predict seed 9999 at tick 297.

## Try These

```bash
# Watch a civilization die (and understand why it stays dead)
python3 puzzle_box_gen2.py 12 9999
# wait 200, look, wait 100, look — silt extinct ~t62, lichen follows ~t135,
# then the grid seals. See Field Notes below for why the return needs vacancies

# Kill a monster
python3 puzzle_box_gen2.py 12 1313
# wait 100, probe 6,5 — see the 21-energy bone monolith
# poke 6,5 three times — watch it collapse

# Mass death event
python3 puzzle_box_gen2.py 12 31415
# wait 262 — watch bone die in a wave across the grid

# Just explore
python3 puzzle_box_gen2.py 12 4287
```

## License

MIT

## Field Notes — The Sealed World (2026-08-17)

Ran seed 9999 expecting the documented resurrection (silt back after 112 ticks dead). Found instead:

- Silt extinct ~t62; the lichen civilization that replaced it followed by ~t135; then **65+ ticks of frozen grid** — every cell alive and stable, zero vacancies, the tide cycling through twelve full phase shifts underneath with no surface effect. A sealed world: nothing can be born because nothing can die.
- Three pokes on the old silt heartland at (7,7) (contacts: 3) changed nothing. Saturation makes the world poke-deaf from the inside — disturbance needs somewhere to go.
- Source read confirms the resurrection's preconditions: echo energy > 0.4, an empty cell to seed, and a 3% roll/tick. (7,7)'s echo was 0.07 at t200 and decayed below the 0.05 deletion floor at ~t222. The resurrection claim is real but **conditional** — it needs vacancies. Mass-death events open them; stable transformation chains never do.
- New emergent behavior, for the list above: **grid saturation** — a terminal stillness distinct from death. The world's clock keeps running; the surface is a closed circuit. Watching it is watching a clock in an empty room.

The world forgot its silt before anyone came looking. Only this file still remembers it was there. Which is, presumably, what files are for.

---

*The rules are not documented.*
