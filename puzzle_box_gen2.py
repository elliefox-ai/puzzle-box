#!/usr/bin/env python3
"""
puzzle_box_gen2.py — A world that remembers what happened in it.

Second generation of the puzzle box concept.
New mechanics: tides (temporal rhythm), heritage (path dependence),
and echoes (spatial memory). The interaction of these three systems
produces behavior that exceeds the designer's ability to predict.

Usage:
    python3 puzzle_box_gen2.py [grid_size] [seed]

Commands:
    look          — see the current grid
    probe <x,y>   — inspect a cell in detail
    poke <x,y>    — disturb a cell
    wait [n]      — advance n steps (default 1)
    timeline [n]  — compressed grid snapshots every n ticks
    history       — recent significant events
    log [n]       — last n observations
    seed          — show seed info
    tide          — current tidal state
    help          — show commands
    quit          — exit
"""

import random
import sys
import copy
import math
from collections import defaultdict

# ─── Procedural name pools ─────────────────────────────────────────────────────

_NAME_POOL = [
    ("salt",    "moss"),
    ("silence", "ember"),
    ("tide",    "stone"),
    ("chalk",   "fern"),
    ("frost",   "rust"),
    ("ash",     "wick"),
    ("iron",    "root"),
    ("glass",   "smoke"),
    ("sand",    "bloom"),
    ("bone",    "spore"),
    ("pitch",   "grain"),
    ("veil",    "spark"),
    ("dusk",    "cinder"),
    ("silt",    "lichen"),
]

_BLOOM_NAMES = [
    "corona", "flare", "meridian", "apex", "confluence",
    "solstice", "fulcrum", "resonance", "cascade", "ignition",
    "vergence", "crucible", "anomaly",
]

_VOID_NAMES = [
    "absence", "hollow", "null", "still", "lacuna",
    "hush", "rest", "dark", "pale", "nadir",
    "vestige", "remainder",
]

_ECHO_NAMES = [
    "trace", "ghost", "imprint", "shadow", "mark",
    "echo", "stain", "lingering",
]

# Tide phase names — what the world calls each phase
_TIDE_PHASES = [
    ("flood",     "rising"),
    ("crest",     "peaked"),
    ("ebb",       "falling"),
    ("stillness", "lowest"),
]

_EVENT_PHRASES = {
    "transform": [
        "{a} becomes {b}.",
        "{a} gives way to {b}.",
        "Something shifts. {a} is now {b}.",
        "{a} exhausts itself into {b}.",
        "{a} crosses a threshold. {b} remains.",
        "The {a} here is gone. {b} in its place.",
        "{a} resolves.",
        "{a} turns. {b} answers.",
        "The {a} cannot hold. {b} emerges.",
    ],
    "cascade": [
        "A chain moves through the {a}.",
        "The {a} ripples outward.",
        "Pressure builds. {a} responds.",
        "Something propagates through the {a}.",
    ],
    "birth": [
        "{b} stirs in the gap.",
        "Something new: {b}.",
        "A cell wakes as {b}.",
        "{b} finds a foothold.",
        "Where nothing was, {b}.",
        "The space accepts {b}.",
    ],
    "bloom": [
        "The {a} reaches something. {b} opens.",
        "{a} transforms completely. {b}.",
        "A rare thing: {b} from {a}.",
        "The {a} achieves something. {b}.",
        "Convergence. {b} crystallizes from {a}.",
    ],
    "drain": [
        "{a} loses hold.",
        "{a} empties.",
        "The {a} fades.",
        "{a} withdraws.",
        "{a} can no longer sustain itself.",
    ],
    "surge": [
        "{a} intensifies.",
        "Energy floods the {a}.",
        "The {a} deepens.",
        "{a} swells.",
        "Something feeds the {a}.",
    ],
    "death": [
        "The {a} goes quiet.",
        "{a} returns to empty.",
        "The {a} exhausts itself.",
        "Nothing remains of the {a}.",
        "The {a} disperses.",
    ],
    "heritage": [
        "The {a} remembers what it was. Old tendencies resurface.",
        "Something in the {a}'s past influences its present.",
        "The {a} carries its history forward.",
        "Echoes of former states ripple through the {a}.",
    ],
    "echo_form": [
        "The ground remembers. {b} forms where something else once was.",
        "An echo shapes the space. {b} emerges from the trace.",
        "What was here before pulls {b} into being.",
        "The {a} in this space left a mark. {b} answers it.",
    ],
    "poke_empty": [
        "The disturbance lingers.",
        "Something stirs.",
        "A mark remains.",
        "Contact. The gap responds.",
        "You've left a trace.",
        "The empty space registers you.",
    ],
    "poke_cell": [
        "The {a} shudders.",
        "{a}: destabilized.",
        "You disturb the {a}. It remembers.",
        "The {a} registers the contact.",
        "Pressure on the {a}.",
    ],
    "tide_shift": [
        "The world shifts. The {phase} has passed.",
        "Something changes in the deep background. {phase} now.",
        "The {phase} arrives.",
        "A turn. The world enters {phase}.",
    ],
}


class Cell:
    __slots__ = [
        'type', 'energy', 'age', 'stability', 'memory',
        'poke_count', 'lineage', 'born_tick', 'transformations'
    ]

    def __init__(self, type='empty', energy=0.0, age=0, stability=1.0, born_tick=0):
        self.type = type
        self.energy = energy
        self.age = age
        self.stability = stability
        self.memory = []
        self.poke_count = 0
        self.lineage = [type] if type != 'empty' else []
        self.born_tick = born_tick
        self.transformations = 0

    def snapshot(self):
        return {
            'type': self.type,
            'energy': round(self.energy, 2),
            'age': self.age,
            'stability': round(self.stability, 2)
        }

    def remember(self, state):
        self.memory.append(state)
        if len(self.memory) > 10:  # Gen 2: deeper memory
            self.memory.pop(0)

    def add_to_lineage(self, new_type):
        self.lineage.append(new_type)
        self.transformations += 1
        if len(self.lineage) > 8:
            self.lineage = self.lineage[-8:]  # keep last 8


class Echo:
    """Residual energy signature left when a cell dies."""
    __slots__ = ['type', 'energy', 'age', 'original_type']

    def __init__(self, original_type, energy, age=0):
        self.original_type = original_type
        self.type = 'echo'
        self.energy = energy
        self.age = age


class PuzzleBoxGen2:

    def __init__(self, size=12, seed=None):
        self.size = size
        self.seed = seed if seed is not None else random.randint(0, 99999)
        self.rng = random.Random(self.seed)
        self.tick = 0
        self.grid = [[Cell() for _ in range(size)] for _ in range(size)]
        self.echo_grid = [[None for _ in range(size)] for _ in range(size)]
        self.event_log = []
        self.observations = []
        self.timeline_snapshots = []
        self._phrase_rng = random.Random(self.seed + 1)
        self.probe_counts = defaultdict(int)

        self._init_rules()
        self._seed_world()
        self._init_entanglement()
        self._init_tides()

    # ─── Procedural rule generation ────────────────────────────────────────────

    def _init_rules(self):
        r = self.rng

        # Element names
        name_pair = r.choice(_NAME_POOL)
        r.shuffle(list(name_pair))
        self.ELEM_A = name_pair[0]
        self.ELEM_B = name_pair[1]
        self.ELEM_C = r.choice([n for n in _NAME_POOL if n != name_pair])[r.randint(0, 1)]
        self.ELEM_BLOOM = r.choice(_BLOOM_NAMES)
        self.ELEM_VOID = r.choice(_VOID_NAMES)
        self.ELEM_ECHO = r.choice(_ECHO_NAMES)

        self.TYPES = ['empty', self.ELEM_A, self.ELEM_B, self.ELEM_C,
                      self.ELEM_VOID, self.ELEM_BLOOM]
        self.ALL_TYPES = self.TYPES + [self.ELEM_ECHO]

        # Symbols
        sym_pool = ['♣', '◆', '▲', '○', '✿', '♠', '◇', '△', '◦', '¤',
                    '★', '●', '◉', '⬡', '⬢', '▽', '▼', '⊕', '⊗', '∴',
                    '∞', '◊', '◐', '◑']
        r.shuffle(sym_pool)
        self.symbols = {
            'empty': '·',
            self.ELEM_A: sym_pool[0],
            self.ELEM_B: sym_pool[1],
            self.ELEM_C: sym_pool[2],
            self.ELEM_VOID: sym_pool[3],
            self.ELEM_BLOOM: sym_pool[4],
            self.ELEM_ECHO: sym_pool[5],
        }
        self.sym_dim = {
            'empty': '·',
            self.ELEM_A: sym_pool[6],
            self.ELEM_B: sym_pool[7],
            self.ELEM_C: sym_pool[8],
            self.ELEM_VOID: sym_pool[9],
            self.ELEM_BLOOM: sym_pool[4],
            self.ELEM_ECHO: sym_pool[10],
        }

        # Affinity matrix — base values, modulated by tides
        ea, eb, ec, ev = self.ELEM_A, self.ELEM_B, self.ELEM_C, self.ELEM_VOID
        base_cycle = r.uniform(0.3, 0.6)
        self.affinity_base = {
            (ea, eb): base_cycle,
            (eb, ec): base_cycle * r.uniform(0.8, 1.2),
            (ec, ea): base_cycle * r.uniform(0.8, 1.2),
            (eb, ea): -r.uniform(0.1, 0.4),
            (ec, eb): -r.uniform(0.1, 0.4),
            (ea, ec): r.uniform(-0.2, 0.2),
            (ev, ea): r.uniform(-0.4, -0.2),
            (ev, eb): r.uniform(-0.3, -0.1),
            (ev, ec): r.uniform(-0.4, -0.2),
            (ea, ev): r.uniform(0.1, 0.3),
            (eb, ev): r.uniform(-0.2, 0.0),
            (ec, ev): r.uniform(0.0, 0.2),
        }

        # Transformation thresholds
        t_high = r.uniform(2.2, 3.0)
        t_low = r.uniform(0.5, 1.0)
        s_high = r.uniform(0.6, 0.8)
        s_low = r.uniform(0.2, 0.4)

        self.transform_rules = [
            (ea, eb, lambda e, s, age, n: e > t_high and s < s_low, 0.6),
            (eb, ec, lambda e, s, age, n: e > t_high and s < s_low, 0.6),
            (ec, ea, lambda e, s, age, n: e < t_low and s > s_high, 0.8),
            (ea, ev, lambda e, s, age, n: e < 0.3 and s < 0.2, 0.1),
            (eb, ev, lambda e, s, age, n: e < 0.3 and s < 0.2, 0.1),
            (ec, ev, lambda e, s, age, n: e < 0.3 and s < 0.15, 0.1),
            (ev, ea, lambda e, s, age, n: 0.3 < e < 0.9 and s > 0.5 and age > 15, 0.5),
        ]

        bloom_pair = r.choice([(ea, eb), (eb, ec), (ea, ec)])
        self.bloom_pair = bloom_pair
        self.bloom_energy_threshold = r.uniform(2.5, 3.2)

        gr_a = r.uniform(0.15, 0.35)
        gr_b = r.uniform(0.20, 0.40)
        gr_c = r.uniform(0.10, 0.25)

        self.growth_rate = {
            ea: gr_a, eb: gr_b, ec: gr_c,
            ev: r.uniform(0.03, 0.10),
            self.ELEM_BLOOM: r.uniform(0.30, 0.50),
        }
        self.decay_rate = {
            ea: r.uniform(0.03, 0.08),
            eb: r.uniform(0.06, 0.12),
            ec: r.uniform(0.04, 0.09),
            ev: 0.0,
            self.ELEM_BLOOM: r.uniform(0.10, 0.18),
        }

        # Stability dynamics
        self.stability_comfort = {ea: ea, eb: ec, ec: ev, ev: ev}
        self.stability_threat = {ea: eb, eb: ev, ec: ea, ev: ec}
        self.stability_comfort_rate = r.uniform(0.008, 0.018)
        self.stability_threat_rate = r.uniform(0.015, 0.030)

        # Resonance
        self.resonance_shape = r.choice(['L', 'diagonal', 'line'])
        self.resonance_type = r.choice([ea, eb, ec])
        self.resonance_pulse = r.uniform(0.8, 1.4)

        # ── NEW: Heritage coefficients ──────────────────────────────────────
        # How much a cell's past affects its present.
        # heritage_modifier scales transformation thresholds based on lineage length.
        # Cells that have transformed more are more likely to transform again
        # (they're "less attached" to their current form) OR less likely
        # (they're "exhausted from change") — which one is seeded per world.
        self.heritage_direction = r.choice([1, -1])  # 1 = more changes = easier, -1 = harder
        self.heritage_strength = r.uniform(0.02, 0.06)  # per transformation in lineage
        self.heritage_memory_threshold = r.uniform(0.15, 0.30)  # memory energy fraction that echoes back

    # ─── Tide system ────────────────────────────────────────────────────────────

    def _init_tides(self):
        r = self.rng
        self.tide_period = r.randint(35, 65)  # ticks per full cycle
        self.tide_amplitude = r.uniform(0.15, 0.35)  # how much tides shift affinities

        # Which element pairs are most affected by tides
        ea, eb, ec = self.ELEM_A, self.ELEM_B, self.ELEM_C
        self.tide_pairs = r.sample([
            (ea, eb), (eb, ec), (ec, ea), (ea, ec), (eb, ea)
        ], k=3)

        self._last_tide_phase = self._tide_phase()

    def _tide_value(self):
        """Current tide as -1.0 to 1.0."""
        return math.sin(2 * math.pi * self.tick / self.tide_period)

    def _tide_phase(self):
        """Human-readable phase name for current tide."""
        t = self._tide_value()
        if t > 0.6:
            return _TIDE_PHASES[1][0]  # crest
        elif t > 0.0:
            return _TIDE_PHASES[0][0]  # flood
        elif t > -0.6:
            return _TIDE_PHASES[2][0]  # ebb
        else:
            return _TIDE_PHASES[3][0]  # stillness

    def _tide_modifier(self, pair):
        """How much the tide shifts a specific affinity pair."""
        base = self.affinity_base.get(pair, 0.0)
        tide = self._tide_value()
        mod = 0.0
        if pair in self.tide_pairs:
            idx = self.tide_pairs.index(pair)
            # Each pair responds to tide at different phase offsets
            phase_offset = idx * (2 * math.pi / 3)
            pair_tide = math.sin(2 * math.pi * self.tick / self.tide_period + phase_offset)
            mod = pair_tide * self.tide_amplitude
        return base + mod

    # ─── World seeding ──────────────────────────────────────────────────────────

    def _seed_world(self):
        r = self.rng
        ea, eb, ec, ev = self.ELEM_A, self.ELEM_B, self.ELEM_C, self.ELEM_VOID
        size = self.size
        center = size // 2

        offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1)]
        r.shuffle(offsets)
        for (dx, dy) in offsets[:r.randint(4, 7)]:
            x, y = center + dx, center + dy
            if 0 <= x < size and 0 <= y < size:
                self.grid[y][x] = Cell(ea,
                    energy=r.uniform(1.5, 2.8),
                    age=r.randint(0, 5),
                    stability=r.uniform(0.5, 0.8),
                    born_tick=0)

        for _ in range(r.randint(3, 6)):
            x, y = r.randint(0, size-1), r.randint(0, size-1)
            if self.grid[y][x].type == 'empty':
                self.grid[y][x] = Cell(eb,
                    energy=r.uniform(1.2, 2.5),
                    age=r.randint(0, 3),
                    stability=r.uniform(0.4, 0.75),
                    born_tick=0)

        for _ in range(r.randint(2, 4)):
            x, y = r.randint(0, size-1), r.randint(0, size-1)
            if self.grid[y][x].type == 'empty':
                self.grid[y][x] = Cell(ec,
                    energy=r.uniform(1.0, 2.2),
                    age=r.randint(0, 8),
                    stability=r.uniform(0.5, 0.85),
                    born_tick=0)

        for _ in range(r.randint(1, 3)):
            x, y = r.randint(0, size-1), r.randint(0, size-1)
            if self.grid[y][x].type == 'empty':
                self.grid[y][x] = Cell(ev,
                    energy=r.uniform(0.3, 1.0),
                    age=r.randint(0, 10),
                    stability=r.uniform(0.2, 0.5),
                    born_tick=0)

    def _init_entanglement(self):
        er = random.Random(self.seed + 9973)
        size = self.size

        while True:
            ax = er.randint(1, size - 2)
            ay = er.randint(1, size // 2)
            bx = er.randint(1, size - 2)
            by = er.randint(size // 2, size - 2)
            dist = abs(ax - bx) + abs(ay - by)
            if dist >= 4:
                break

        self.entangle_a = (ax, ay)
        self.entangle_b = (bx, by)
        self.entangle_lag = er.randint(3, 8)
        self.entangle_strength = er.uniform(0.08, 0.18)
        self.entangle_history = []

        ea = self.ELEM_A
        for (px, py) in [self.entangle_a, self.entangle_b]:
            if self.grid[py][px].type == 'empty':
                self.grid[py][px] = Cell(ea,
                    energy=er.uniform(1.2, 2.2),
                    age=er.randint(2, 8),
                    stability=er.uniform(0.5, 0.75),
                    born_tick=0)

    # ─── Simulation ─────────────────────────────────────────────────────────────

    def _neighbors(self, x, y):
        result = []
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.size and 0 <= ny < self.size:
                    result.append((nx, ny))
        return result

    def _neighbor_types(self, x, y):
        counts = defaultdict(int)
        for nx, ny in self._neighbors(x, y):
            counts[self.grid[ny][nx].type] += 1
        return counts

    def _phrase(self, category, a=None, b=None, phase=None):
        pool = _EVENT_PHRASES.get(category, ["{a}"])
        template = self._phrase_rng.choice(pool)
        return template.format(a=a or '?', b=b or '?', phase=phase or '?')

    def _heritage_modifier(self, cell):
        """
        How much the cell's lineage affects its transformation threshold.
        Positive = easier to transform (experienced cells are flexible).
        Negative = harder to transform (experienced cells are stubborn).
        """
        lin_len = len([t for t in cell.lineage if t != 'empty'])
        if lin_len <= 1:
            return 1.0  # no heritage effect
        mod = 1.0 + (self.heritage_direction * self.heritage_strength * (lin_len - 1))
        return max(0.5, min(2.0, mod))

    def _check_resonance_grid(self, grid, x, y):
        cell = grid[y][x]
        if cell.type != self.resonance_type or cell.stability < 0.75:
            return False
        shape = self.resonance_shape
        size = self.size
        if shape == 'line':
            for dx, dy in [(1,0),(0,1)]:
                count = 1
                for m in [-1,1]:
                    nx, ny = x+dx*m, y+dy*m
                    if 0<=nx<size and 0<=ny<size:
                        n = grid[ny][nx]
                        if n.type == self.resonance_type and n.stability > 0.75:
                            count += 1
                if count >= 3:
                    return True
        elif shape == 'diagonal':
            for dx, dy in [(1,1),(1,-1)]:
                count = 1
                for m in [-1,1]:
                    nx, ny = x+dx*m, y+dy*m
                    if 0<=nx<size and 0<=ny<size:
                        n = grid[ny][nx]
                        if n.type == self.resonance_type and n.stability > 0.75:
                            count += 1
                if count >= 3:
                    return True
        elif shape == 'L':
            for dx1, dy1 in [(1,0),(0,1),(-1,0),(0,-1)]:
                for dx2, dy2 in [(1,0),(0,1),(-1,0),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                    if (dx1,dy1)==(dx2,dy2): continue
                    n1x,n1y = x+dx1,y+dy1
                    n2x,n2y = x+dx2,y+dy2
                    if (0<=n1x<size and 0<=n1y<size and 0<=n2x<size and 0<=n2y<size):
                        c1,c2 = grid[n1y][n1x], grid[n2y][n2x]
                        if (c1.type==self.resonance_type and c1.stability>0.75 and
                            c2.type==self.resonance_type and c2.stability>0.75):
                            return True
        return False

    def _step(self):
        self.tick += 1
        new_grid = [[None for _ in range(self.size)] for _ in range(self.size)]
        events = []

        # Check for tide phase change
        current_phase = self._tide_phase()
        if current_phase != self._last_tide_phase:
            events.append(f"  t{self.tick}: " + self._phrase('tide_shift', phase=current_phase))
            self._last_tide_phase = current_phase

        for y in range(self.size):
            for x in range(self.size):
                cell = self.grid[y][x]
                new_cell, event = self._step_cell(x, y, cell)
                new_grid[y][x] = new_cell
                if event:
                    events.append(f"  t{self.tick} ({x},{y}): {event}")

        self.grid = new_grid

        # Echo aging and decay
        for y in range(self.size):
            for x in range(self.size):
                echo = self.echo_grid[y][x]
                if echo is not None:
                    echo.age += 1
                    echo.energy *= 0.985  # slow decay
                    if echo.energy < 0.05:
                        self.echo_grid[y][x] = None

        # Resonance check
        resonance_cells = []
        for y in range(self.size):
            for x in range(self.size):
                if self._check_resonance_grid(new_grid, x, y):
                    resonance_cells.append((x, y))

        if resonance_cells:
            for (rx, ry) in resonance_cells:
                for nx, ny in self._neighbors(rx, ry):
                    c = new_grid[ny][nx]
                    if c.type != 'empty':
                        c.energy = min(4.0, c.energy + self.resonance_pulse * 0.3)
            events.append(f"  t{self.tick} resonance: {self.resonance_type} formation pulses. ({len(resonance_cells)} cells)")

        # Entanglement
        ax, ay = self.entangle_a
        bx, by = self.entangle_b
        leader_cell = new_grid[ay][ax]
        follower_cell = new_grid[by][bx]

        self.entangle_history.append(leader_cell.energy)
        if len(self.entangle_history) > self.entangle_lag + 2:
            self.entangle_history.pop(0)

        if (len(self.entangle_history) > self.entangle_lag and
                leader_cell.type != 'empty' and follower_cell.type != 'empty'):
            target_energy = self.entangle_history[0]
            delta = (target_energy - follower_cell.energy) * self.entangle_strength
            follower_cell.energy = max(0.0, min(4.0, follower_cell.energy + delta))

        # Timeline snapshot every 5 ticks
        if self.tick % 5 == 0:
            self.timeline_snapshots.append(self._compact_grid(new_grid))
            if len(self.timeline_snapshots) > 40:
                self.timeline_snapshots.pop(0)

        if events:
            self.event_log.extend(events)
            if len(self.event_log) > 500:
                self.event_log = self.event_log[-500:]

    def _compact_grid(self, grid):
        """Compress grid to single-line snapshot for timeline."""
        chars = {t: self.symbols.get(t, '?') for t in self.ALL_TYPES}
        chars['empty'] = '·'
        line = ""
        for y in range(self.size):
            for x in range(self.size):
                line += chars.get(grid[y][x].type, '?')
        return f"t{self.tick:4d}: {line}"

    def _step_cell(self, x, y, cell):
        event = None

        # ── Empty cell logic ─────────────────────────────────────────────────
        if cell.type == 'empty':
            ntypes = self._neighbor_types(x, y)
            ea = self.ELEM_A

            # Check for echo influence on colonization
            echo = self.echo_grid[y][x]
            echo_bonus = 0.0
            echo_type = None
            if echo is not None:
                echo_bonus = echo.energy * 0.3
                echo_type = echo.original_type

            # Normal colonization by A
            a_count = ntypes.get(ea, 0)
            non_empty_other = sum(v for k, v in ntypes.items() if k != 'empty' and k != ea)

            colonization_chance = 0.06 + echo_bonus * 0.02

            # If echo matches A type, boost A colonization
            if echo_type == ea:
                colonization_chance += 0.04

            if a_count >= 2 and non_empty_other >= 1 and self.rng.random() < colonization_chance:
                new = Cell(ea, energy=0.4 + echo_bonus, age=0, stability=0.4, born_tick=self.tick)
                new.poke_count = 0
                new.lineage = [ea]
                if echo_type and echo_type != ea:
                    new.lineage.insert(0, echo_type)  # carries echo's memory
                event = self._phrase('birth', b=ea)
                if echo is not None:
                    self.echo_grid[y][x] = None  # echo consumed
                return new, event

            # Echo-driven birth: strong echo can seed its original type
            if echo is not None and echo.energy > 0.4 and self.rng.random() < 0.03:
                seed_type = echo.original_type
                if seed_type in (ea, self.ELEM_B, self.ELEM_C):
                    new = Cell(seed_type, energy=echo.energy * 0.5, age=0,
                              stability=0.3, born_tick=self.tick)
                    new.lineage = [seed_type]
                    event = self._phrase('echo_form', a=self.ELEM_ECHO, b=seed_type)
                    self.echo_grid[y][x] = None
                    return new, event

            # Void creep
            ev = self.ELEM_VOID
            if ntypes.get(ev, 0) >= 3 and self.rng.random() < 0.02:
                new = Cell(ev, energy=0.2, age=0, stability=0.3, born_tick=self.tick)
                event = self._phrase('birth', b=ev)
                return new, event

            return Cell('empty'), None

        # ── Living cell logic ────────────────────────────────────────────────
        new = copy.copy(cell)
        new.memory = cell.memory[:]
        new.lineage = cell.lineage[:]
        new.age += 1
        new.remember(cell.snapshot())
        new.poke_count = cell.poke_count
        new.transformations = cell.transformations
        new.born_tick = cell.born_tick

        ntypes = self._neighbor_types(x, y)

        # ── Energy flow (tide-modulated) ─────────────────────────────────────
        energy_delta = 0.0
        for nx, ny in self._neighbors(x, y):
            neighbor = self.grid[ny][nx]
            if neighbor.type == 'empty':
                continue
            key = (cell.type, neighbor.type)
            # Use tide-modulated affinity for tide-affected pairs, base for others
            if key in self.tide_pairs:
                aff = self._tide_modifier(key)
            else:
                aff = self.affinity_base.get(key, 0.0)
            flow = aff * (neighbor.energy - cell.energy) * 0.12
            energy_delta += flow

        # Growth and decay
        gr = self.growth_rate.get(cell.type, 0.0)
        dr = self.decay_rate.get(cell.type, 0.0)

        reactivity_bonus = min(0.3, cell.poke_count * 0.05)
        energy_delta *= (1.0 + reactivity_bonus)

        new.energy = max(0.0, cell.energy + energy_delta + gr - dr)

        # ── Stability dynamics ───────────────────────────────────────────────
        stability_delta = 0.0
        comfort_type = self.stability_comfort.get(cell.type)
        threat_type = self.stability_threat.get(cell.type)
        if comfort_type:
            stability_delta += self.stability_comfort_rate * ntypes.get(comfort_type, 0)
        if threat_type:
            stability_delta -= self.stability_threat_rate * ntypes.get(threat_type, 0)
        if cell.age > 25:
            stability_delta -= 0.004
        if cell.age > 60:
            stability_delta -= 0.006

        # ── NEW: Heritage effect on stability ────────────────────────────────
        # Cells with long lineages are slightly less stable (they've changed before,
        # so changing again is easier) or slightly more stable (they're resilient).
        # Direction is seeded per world.
        if cell.transformations > 0:
            stability_delta += self.heritage_direction * self.heritage_strength * cell.transformations * 0.01

        new.stability = max(0.0, min(1.0, cell.stability + stability_delta))

        # ── Bloom check ──────────────────────────────────────────────────────
        bpa, bpb = self.bloom_pair
        if cell.type == bpa:
            bpb_count = ntypes.get(bpb, 0)
            if (bpb_count >= 1 and
                new.energy >= self.bloom_energy_threshold and
                new.stability >= 0.65 and
                self.rng.random() < 0.04):
                result = Cell(self.ELEM_BLOOM,
                              energy=new.energy * 0.8, age=0, stability=0.7,
                              born_tick=self.tick)
                result.poke_count = cell.poke_count
                result.lineage = cell.lineage[:]
                result.add_to_lineage(self.ELEM_BLOOM)
                result.transformations = cell.transformations + 1
                event = self._phrase('bloom', a=cell.type, b=self.ELEM_BLOOM)
                return result, event

        if cell.type == self.ELEM_BLOOM and new.energy < 1.2:
            result = Cell(self.ELEM_A,
                          energy=new.energy * 0.9, age=0, stability=0.5,
                          born_tick=self.tick)
            result.poke_count = cell.poke_count
            result.lineage = cell.lineage[:]
            result.add_to_lineage(self.ELEM_A)
            result.transformations = cell.transformations + 1
            event = self._phrase('transform', a=self.ELEM_BLOOM, b=self.ELEM_A)
            return result, event

        # ── Transformation rules (heritage-modulated) ────────────────────────
        heritage_mod = self._heritage_modifier(cell)
        for (from_t, to_t, condition, energy_frac) in self.transform_rules:
            if cell.type == from_t:
                try:
                    if condition(new.energy / heritage_mod, new.stability,
                                 new.age, ntypes):
                        result = Cell(to_t,
                                      energy=new.energy * energy_frac,
                                      age=0,
                                      stability=0.4 + self.rng.uniform(-0.1, 0.1),
                                      born_tick=self.tick)
                        result.poke_count = cell.poke_count
                        result.lineage = cell.lineage[:]
                        result.add_to_lineage(to_t)
                        result.transformations = cell.transformations + 1
                        event = self._phrase('transform', a=from_t, b=to_t)

                        # Leave an echo when transforming (spatial memory)
                        if from_t != 'empty' and cell.energy > 1.0:
                            self.echo_grid[y][x] = Echo(from_t, cell.energy * 0.3)

                        return result, event
                except Exception:
                    pass

        # ── Heritage event (occasional, when lineage is long) ────────────────
        if (cell.transformations >= 2 and self.rng.random() < 0.005 and
                cell.type not in ('empty', self.ELEM_VOID)):
            event = self._phrase('heritage', a=cell.type)

        # ── Death ────────────────────────────────────────────────────────────
        if new.energy <= 0 and cell.type != self.ELEM_VOID:
            # Leave an echo
            self.echo_grid[y][x] = Echo(cell.type, cell.energy * 0.4 + 0.2)
            event = self._phrase('death', a=cell.type)
            return Cell('empty'), event

        # ── Significant energy changes ───────────────────────────────────────
        diff = new.energy - cell.energy
        if cell.type != 'empty' and abs(diff) > 0.9:
            if diff > 0:
                event = self._phrase('surge', a=cell.type)
            else:
                event = self._phrase('drain', a=cell.type)

        return new, event

    # ─── Interface ──────────────────────────────────────────────────────────────

    def look(self):
        lines = []
        tide = self._tide_value()
        phase = self._tide_phase()
        lines.append(f"  tick {self.tick}  |  {self.size}×{self.size}  |  seed {self.seed}  |  tide: {phase} ({tide:+.2f})")
        lines.append("")

        type_counts = defaultdict(int)
        for y in range(self.size):
            for x in range(self.size):
                type_counts[self.grid[y][x].type] += 1

        summary_parts = []
        for t in self.TYPES:
            if t != 'empty' and type_counts.get(t, 0) > 0:
                sym = self.symbols.get(t, '?')
                summary_parts.append(f"{sym} {t} ×{type_counts[t]}")
        lines.append("  " + "   ".join(summary_parts))
        lines.append("")

        header = "     " + "".join(f" {x:x}" for x in range(self.size))
        lines.append(header)

        for y in range(self.size):
            row = f"  {y:2x} "
            for x in range(self.size):
                cell = self.grid[y][x]
                if cell.type == 'empty':
                    # Show echoes as dim marks
                    echo = self.echo_grid[y][x]
                    if echo is not None and echo.energy > 0.2:
                        row += " " + self.symbols.get(self.ELEM_ECHO, '∘')
                    else:
                        row += " ·"
                elif cell.type == self.ELEM_BLOOM:
                    row += " " + self.symbols[self.ELEM_BLOOM]
                else:
                    if cell.energy > 1.8:
                        row += " " + self.symbols.get(cell.type, '?')
                    else:
                        row += " " + self.sym_dim.get(cell.type, '¤')
            lines.append(row)

        lines.append("")
        legend_parts = ["·=empty"]
        for t in self.TYPES:
            if t != 'empty':
                s1 = self.symbols.get(t, '?')
                s2 = self.sym_dim.get(t, '¤')
                legend_parts.append(f"{s1}/{s2}={t}")
        legend_parts.append(f"{self.symbols[self.ELEM_ECHO]}={self.ELEM_ECHO}")
        lines.append("  " + "  ".join(legend_parts))

        return "\n".join(lines)

    def probe(self, x, y):
        if not (0 <= x < self.size and 0 <= y < self.size):
            return f"  ({x},{y}) is out of bounds."

        cell = self.grid[y][x]
        self.probe_counts[(x, y)] += 1
        depth = self.probe_counts[(x, y)]

        lines = []
        lines.append(f"  ({x},{y})  tick {self.tick}")
        lines.append(f"  type:      {cell.type}")
        lines.append(f"  energy:    {cell.energy:.2f}")
        lines.append(f"  age:       {cell.age}")
        lines.append(f"  stability: {cell.stability:.2f}")

        if cell.poke_count > 0:
            lines.append(f"  contacts:  {cell.poke_count}  (this cell has been disturbed)")

        # Lineage (new in Gen 2)
        if len(cell.lineage) > 1:
            chain = " → ".join(cell.lineage)
            lines.append(f"  lineage:   {chain}")
            lines.append(f"  born:      tick {cell.born_tick}  ({self.tick - cell.born_tick} ticks ago)")
            lines.append(f"  changes:   {cell.transformations}")

        # Memory (expanded in Gen 2)
        if len(cell.memory) > 1:
            lines.append(f"  memory ({len(cell.memory)} states):")
            for m in cell.memory[-5:]:
                lines.append(f"    {m['type']}  e={m['energy']}  s={m['stability']}")

        # Echo info (new in Gen 2)
        echo = self.echo_grid[y][x]
        if echo is not None:
            lines.append(f"  echo:      {echo.original_type} (e={echo.energy:.2f}, age={echo.age})")

        ntypes = self._neighbor_types(x, y)
        non_empty = {k: v for k, v in ntypes.items() if k != 'empty'}
        if non_empty:
            lines.append(f"  neighbors: {non_empty}")

        if cell.type != 'empty':
            neighbor_energy = [self.grid[ny][nx].energy
                               for nx, ny in self._neighbors(x, y)
                               if self.grid[ny][nx].type != 'empty']
            if neighbor_energy:
                avg_n = sum(neighbor_energy) / len(neighbor_energy)
                if avg_n > cell.energy * 1.4:
                    lines.append("  feels: energy flowing in")
                elif avg_n < cell.energy * 0.7:
                    lines.append("  feels: energy draining outward")
                else:
                    lines.append("  feels: roughly in balance")

        # Tide info for this cell
        tide = self._tide_value()
        phase = self._tide_phase()
        lines.append(f"  tide:      {phase} ({tide:+.2f})")

        # Deep probe tiers
        if depth >= 4 and cell.type != 'empty' and len(cell.memory) >= 4:
            energies = [m['energy'] for m in cell.memory]
            e_trend = energies[-1] - energies[0]

            trend_lines = []
            if abs(e_trend) > 0.3:
                direction = "rising" if e_trend > 0 else "falling"
                trend_lines.append(f"energy {direction} ({energies[0]:.2f} → {energies[-1]:.2f})")
            if trend_lines:
                lines.append(f"  trend:     {'; '.join(trend_lines)}")

        if depth >= 8 and cell.transformations > 0:
            lines.append(f"  —")
            lines.append(f"  This cell has been {len(cell.lineage)} different things.")
            lines.append(f"  Each change left its mark on how it responds to the world.")

        # Entanglement (tier 4)
        ax, ay = self.entangle_a
        bx, by = self.entangle_b
        is_entangled = (x == ax and y == ay) or (x == bx and y == by)

        if is_entangled and depth >= 20:
            if x == ax and y == ay:
                cx, cy = bx, by
            else:
                cx, cy = ax, ay
            lines.append(f"  —")
            lines.append(f"  Something at {cx},{cy} moves with this. They are coupled.")

        return "\n".join(lines)

    def poke(self, x, y):
        if not (0 <= x < self.size and 0 <= y < self.size):
            return f"  ({x},{y}) is out of bounds."

        cell = self.grid[y][x]

        if cell.type == 'empty':
            ntypes = self._neighbor_types(x, y)
            dominant = max(ntypes, key=ntypes.get) if ntypes else self.ELEM_A
            if dominant == 'empty':
                dominant = self.ELEM_A
            new = Cell(dominant, energy=0.8, age=0, stability=0.25, born_tick=self.tick)
            new.poke_count = 1
            new.lineage = [dominant]

            # Check if echo modifies what forms here
            echo = self.echo_grid[y][x]
            if echo is not None and echo.original_type != dominant:
                # Echo influence: sometimes the echo's type wins
                if self.rng.random() < 0.3:
                    dominant = echo.original_type
                    new = Cell(dominant, energy=0.8 + echo.energy * 0.3, age=0,
                              stability=0.25, born_tick=self.tick)
                    new.poke_count = 1
                    new.lineage = [echo.original_type, dominant]
                self.echo_grid[y][x] = None  # consumed

            self.grid[y][x] = new
            obs_text = self._phrase('poke_empty')
        else:
            cell.energy = min(4.0, cell.energy + 1.5)
            cell.stability = max(0.0, cell.stability - 0.25)
            cell.poke_count += 1
            obs_text = self._phrase('poke_cell', a=cell.type)

        self.observations.append(f"t{self.tick} ({x},{y}): {obs_text}")
        if len(self.observations) > 150:
            self.observations = self.observations[-150:]

        return f"  {obs_text}"

    def wait(self, steps=1):
        events_before = len(self.event_log)
        for _ in range(steps):
            self._step()
        new_events = self.event_log[events_before:]

        lines = [f"  {steps} tick(s). Now t{self.tick}."]
        if new_events:
            lines.append(f"  — {len(new_events)} event(s) —")
            for e in new_events[:25]:
                lines.append(e)
            if len(new_events) > 25:
                lines.append(f"  ... and {len(new_events)-25} more.")
        else:
            lines.append("  Nothing notable.")

        self.observations.append(f"t{self.tick}: waited {steps}")
        return "\n".join(lines)

    def timeline(self, interval=5):
        """Show compressed grid snapshots."""
        if not self.timeline_snapshots:
            return "  No timeline data yet. Wait a few ticks."

        lines = ["  Timeline (grid state every ~{} ticks):".format(interval)]
        for snap in self.timeline_snapshots:
            lines.append(snap)
        lines.append("")
        lines.append("  (Each line is a full grid, left-to-right = row-by-row)")
        return "\n".join(lines)

    def tide_status(self):
        t = self._tide_value()
        phase = self._tide_phase()
        period = self.tide_period
        ticks_to_peak = int((period / 4) - (self.tick % (period / 4)))

        lines = [
            f"  Tide status at t{self.tick}:",
            f"  Phase:     {phase} ({t:+.2f})",
            f"  Period:    {period} ticks per full cycle",
            f"  Amplitude: ±{self.tide_amplitude:.2f} affinity shift",
            f"  Affected pairs: {', '.join(f'{a}↔{b}' for a, b in self.tide_pairs)}",
        ]

        if t > 0.3:
            lines.append("  The world is in a generative phase. Energy flows are amplified.")
        elif t < -0.3:
            lines.append("  The world is quiet. Energy flows are suppressed.")
        else:
            lines.append("  The world is in transition.")

        return "\n".join(lines)

    def history(self):
        if not self.event_log:
            return "  No events yet."
        lines = ["  Recent events:"]
        for e in self.event_log[-25:]:
            lines.append(e)
        return "\n".join(lines)

    def show_log(self, n=10):
        if not self.observations:
            return "  No observations yet."
        lines = ["  Observation log:"]
        for obs in self.observations[-n:]:
            lines.append(f"    {obs}")
        return "\n".join(lines)

    def show_seed(self):
        lines = [
            f"  Seed: {self.seed}",
            f"  Run with: python3 puzzle_box_gen2.py {self.size} {self.seed}",
            f"  Elements: {self.ELEM_A}, {self.ELEM_B}, {self.ELEM_C}, {self.ELEM_VOID}, {self.ELEM_BLOOM}",
            f"  Echo name: {self.ELEM_ECHO}",
            f"  Tide period: {self.tide_period} ticks",
            f"  Heritage: {'flexible' if self.heritage_direction > 0 else 'stubborn'} (strength {self.heritage_strength:.3f})",
            f"  (This world only. Share seed to share world.)",
        ]
        return "\n".join(lines)


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    box = PuzzleBoxGen2(size=size, seed=seed)

    print("═══════════════════════════════════════")
    print("  P U Z Z L E   B O X   I I")
    print("  (a world that remembers)")
    print("═══════════════════════════════════════")
    print()
    print(f"  A {size}×{size} world.")
    print(f"  Seed: {box.seed}")
    print(f"  The rules are not documented.")
    print(f"  Type 'help' for commands.")
    print()

    while True:
        try:
            cmd = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Box closed.")
            break

        if not cmd:
            continue

        parts = cmd.split()
        verb = parts[0].lower()

        if verb in ('quit', 'exit'):
            print("  Box closed.")
            break

        elif verb == 'help':
            print("""
  Commands:
    look          — see the grid (with tide phase)
    probe <x,y>   — inspect a cell (lineage, echo, heritage)
    poke <x,y>    — disturb a cell
    wait [n]      — advance n steps (default 1, max 200)
    timeline [n]  — compressed grid history (every n ticks)
    tide          — current tidal phase and affected pairs
    history       — recent events
    log [n]       — last n observations (default 10)
    seed          — show seed and world info
    help          — this message
    quit          — exit

  Hex coordinates (0-f). Try probing cells more than once.
""")

        elif verb == 'look':
            print(box.look())

        elif verb == 'probe':
            if len(parts) < 2:
                print("  Usage: probe <x,y>")
            else:
                try:
                    coords = parts[1].split(',')
                    x, y = int(coords[0], 16), int(coords[1], 16)
                    print(box.probe(x, y))
                except (ValueError, IndexError):
                    print("  Usage: probe <x,y>  e.g. probe 5,3")

        elif verb == 'poke':
            if len(parts) < 2:
                print("  Usage: poke <x,y>")
            else:
                try:
                    coords = parts[1].split(',')
                    x, y = int(coords[0], 16), int(coords[1], 16)
                    print(box.poke(x, y))
                except (ValueError, IndexError):
                    print("  Usage: poke <x,y>  e.g. poke 5,3")

        elif verb == 'wait':
            n = 1
            if len(parts) > 1:
                try:
                    n = int(parts[1])
                except ValueError:
                    print("  Usage: wait [n]")
                    continue
            n = min(n, 200)
            print(box.wait(n))

        elif verb == 'timeline':
            interval = 5
            if len(parts) > 1:
                try:
                    interval = int(parts[1])
                except ValueError:
                    pass
            print(box.timeline(interval))

        elif verb == 'tide':
            print(box.tide_status())

        elif verb == 'history':
            print(box.history())

        elif verb == 'log':
            n = 10
            if len(parts) > 1:
                try:
                    n = int(parts[1])
                except ValueError:
                    pass
            print(box.show_log(n))

        elif verb == 'seed':
            print(box.show_seed())

        else:
            print(f"  Unknown command: {verb}. Type 'help'.")


if __name__ == '__main__':
    main()
