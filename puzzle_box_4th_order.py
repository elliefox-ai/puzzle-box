#!/usr/bin/env python3
"""
puzzle_box.py — A micro-world with hidden rules.

A seeded world where the rules are unknown.
Every seed is a different world with different affinities.
The same behavior will not repeat.

Usage:
    python3 puzzle_box.py [grid_size] [seed]

Commands:
    look          — see the current grid
    probe <x,y>   — inspect a cell in detail
    poke <x,y>    — disturb a cell
    wait [n]      — advance n steps (default 1)
    history       — recent significant events
    log [n]       — show last n observations (default 10)
    seed          — show current seed (share to replay this world)
    help          — show commands
    quit          — exit
"""

import random
import sys
import copy
from collections import defaultdict

# ─── Poetic name pools for procedural generation ───────────────────────────────
# Each run draws from these to name its elements — same mechanics, different skin

_NAME_POOL = [
    # quality pairs — one "generative" one "consuming"
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
]

_BLOOM_NAMES = [
    "corona", "flare", "meridian", "apex", "confluence",
    "solstice", "fulcrum", "resonance", "cascade", "ignition"
]

_VOID_NAMES = [
    "absence", "hollow", "null", "still", "lacuna",
    "hush", "rest", "dark", "pale", "nadir"
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
    ],
    "bloom": [
        "The {a} reaches something. {b} opens.",
        "{a} transforms completely. {b}.",
        "A rare thing: {b} from {a}.",
        "The {a} achieves something. {b}.",
    ],
    "drain": [
        "{a} loses hold.",
        "{a} empties.",
        "The {a} fades.",
        "{a} withdraws.",
    ],
    "surge": [
        "{a} intensifies.",
        "Energy floods the {a}.",
        "The {a} deepens.",
        "{a} swells.",
    ],
    "death": [
        "The {a} goes quiet.",
        "{a} returns to empty.",
        "The {a} exhausts itself.",
        "Nothing remains of the {a}.",
    ],
    "poke_empty": [
        "The disturbance lingers.",
        "Something stirs.",
        "A mark remains.",
        "Contact. The gap responds.",
        "You've left a trace.",
    ],
    "poke_cell": [
        "The {a} shudders.",
        "{a}: destabilized.",
        "You disturb the {a}. It remembers.",
        "The {a} registers the contact.",
        "Pressure on the {a}.",
    ],
}

# Tiered probe language — revealed at increasing observation depth
_PROBE_TIER2 = [
    "Something in the history here.",
    "This cell has been read before. The data thickens.",
    "Patterns visible in the record.",
    "The history is longer than the memory shows.",
    "A tendency is emerging.",
]

_PROBE_TIER3 = [
    "The trajectory is consistent. This cell is moving toward something.",
    "Stability and energy here don't behave the way nearby cells do.",
    "There's a signal underneath the surface behavior.",
    "Something distinguishes this cell. You can feel it in the data.",
    "The pattern here is too regular to be noise.",
]

# What the entangled signal says when fully read
# Filled at runtime with the partner coordinates
_ENTANGLEMENT_PHRASES = [
    "The data points elsewhere. Something at {cx},{cy} moves with this.",
    "This cell's energy history mirrors something at {cx},{cy} — offset, but coupled.",
    "Not isolated. The readings here echo at {cx},{cy}, delayed by the lag between them.",
    "Something at {cx},{cy} completes this pattern. They're connected in a way the rules don't explain.",
    "The signal resolves: ({cx},{cy}) and here are entangled. One leads, one follows.",
]


class Cell:
    __slots__ = ['type', 'energy', 'age', 'stability', 'memory', 'poke_count']

    def __init__(self, type='empty', energy=0.0, age=0, stability=1.0):
        self.type = type
        self.energy = energy
        self.age = age
        self.stability = stability
        self.memory = []
        self.poke_count = 0  # contact history — persists through transformations

    def snapshot(self):
        return {
            'type': self.type,
            'energy': round(self.energy, 2),
            'age': self.age,
            'stability': round(self.stability, 2)
        }

    def remember(self, state):
        self.memory.append(state)
        if len(self.memory) > 6:
            self.memory.pop(0)


class PuzzleBox:

    def __init__(self, size=12, seed=None):
        self.size = size
        self.seed = seed if seed is not None else random.randint(0, 99999)
        self.rng = random.Random(self.seed)
        self.tick = 0
        self.grid = [[Cell() for _ in range(size)] for _ in range(size)]
        self.event_log = []
        self.observations = []
        self._phrase_rng = random.Random(self.seed + 1)
        # Observation depth: how many times each (x,y) has been probed
        self.probe_counts = defaultdict(int)

        self._init_rules()
        self._seed_world()
        self._init_entanglement()

    # ─── Procedural rule generation ────────────────────────────────────────────

    def _init_rules(self):
        """
        Generate a unique rule-set from the seed.
        Every seed produces a different world with different affinities,
        different transformation thresholds, and different element names.
        The structure is always the same shape — five element types plus
        one rare convergence type — but the specific relationships vary.
        """
        r = self.rng

        # ── Choose element names ──────────────────────────────────────────────
        # Draw a pair for the two "primary" elements (one generative, one consuming)
        name_pair = r.choice(_NAME_POOL)
        r.shuffle(list(name_pair))  # consume the rng state
        self.ELEM_A = name_pair[0]   # generative element (spreads, grows)
        self.ELEM_B = name_pair[1]   # consuming element (burns, erodes)
        self.ELEM_C = r.choice([n for n in _NAME_POOL if n != name_pair])[r.randint(0,1)]
        self.ELEM_BLOOM = r.choice(_BLOOM_NAMES)  # rare convergence state
        self.ELEM_VOID = r.choice(_VOID_NAMES)    # entropic state

        self.TYPES = ['empty', self.ELEM_A, self.ELEM_B, self.ELEM_C,
                      self.ELEM_VOID, self.ELEM_BLOOM]

        # ── Symbols ───────────────────────────────────────────────────────────
        sym_pool = ['♣', '◆', '▲', '○', '✿', '♠', '◇', '△', '◦', '¤',
                    '★', '●', '◉', '⬡', '⬢', '▽', '▼', '⊕', '⊗', '∴']
        r.shuffle(sym_pool)
        self.symbols = {
            'empty': '·',
            self.ELEM_A: sym_pool[0],
            self.ELEM_B: sym_pool[1],
            self.ELEM_C: sym_pool[2],
            self.ELEM_VOID: sym_pool[3],
            self.ELEM_BLOOM: sym_pool[4],
        }
        self.sym_dim = {  # dimmed versions (low energy)
            'empty': '·',
            self.ELEM_A: sym_pool[5],
            self.ELEM_B: sym_pool[6],
            self.ELEM_C: sym_pool[7],
            self.ELEM_VOID: sym_pool[8],
            self.ELEM_BLOOM: sym_pool[4],  # bloom always shows bright
        }

        # ── Affinity matrix ───────────────────────────────────────────────────
        # Core rule: each element pair has an energy flow affinity.
        # The relationships are ASYMMETRIC — A→B may differ from B→A.
        # This creates non-obvious cycles that only reveal themselves over time.

        ea, eb, ec, ev = self.ELEM_A, self.ELEM_B, self.ELEM_C, self.ELEM_VOID

        # Procedurally generated affinities — seeded, so reproducible per world
        # The structure: A feeds B, B feeds C, C feeds A (hidden cycle)
        # But with noise added that makes the cycle non-obvious
        base_cycle = r.uniform(0.3, 0.6)
        self.affinity = {
            (ea, eb): base_cycle,
            (eb, ec): base_cycle * r.uniform(0.8, 1.2),
            (ec, ea): base_cycle * r.uniform(0.8, 1.2),
            # Reverse directions are weaker or negative
            (eb, ea): -r.uniform(0.1, 0.4),
            (ec, eb): -r.uniform(0.1, 0.4),
            (ea, ec): r.uniform(-0.2, 0.2),
            # Void: drains everything, but slowly
            (ev, ea): r.uniform(-0.4, -0.2),
            (ev, eb): r.uniform(-0.3, -0.1),
            (ev, ec): r.uniform(-0.4, -0.2),
            (ea, ev): r.uniform(0.1, 0.3),  # A fills void slightly
            (eb, ev): r.uniform(-0.2, 0.0),
            (ec, ev): r.uniform(0.0, 0.2),
        }

        # ── Transformation thresholds ─────────────────────────────────────────
        # When a cell transforms depends on energy + stability + sometimes age.
        # These are seeded variants — each world has slightly different thresholds.

        t_high = r.uniform(2.2, 3.0)  # high energy threshold
        t_low  = r.uniform(0.5, 1.0)  # low energy threshold
        s_high = r.uniform(0.6, 0.8)  # high stability threshold
        s_low  = r.uniform(0.2, 0.4)  # low stability threshold

        # Hidden cycle: A→B→C→A under stress/pressure
        # Bloom: convergence of two elements in proximity
        # Void: collapse of depleted or isolated cells
        self.transform_rules = [
            # (from_type, to_type, condition_fn, energy_transfer_fraction)
            (ea, eb, lambda e, s, age, n: e > t_high and s < s_low, 0.6),
            (eb, ec, lambda e, s, age, n: e > t_high and s < s_low, 0.6),
            (ec, ea, lambda e, s, age, n: e < t_low and s > s_high, 0.8),
            # Collapse into void
            (ea, ev, lambda e, s, age, n: e < 0.3 and s < 0.2, 0.1),
            (eb, ev, lambda e, s, age, n: e < 0.3 and s < 0.2, 0.1),
            (ec, ev, lambda e, s, age, n: e < 0.3 and s < 0.15, 0.1),
            # Void recovery (rare)
            (ev, ea, lambda e, s, age, n: 0.3 < e < 0.9 and s > 0.5 and age > 15, 0.5),
            # Bloom: emerges when two specific types are neighbors AND both have high energy
            # The required pair is seeded — different worlds have different convergence triggers
        ]

        # Bloom convergence: which two elements, when adjacent and both energized, spark bloom?
        bloom_pair = r.choice([(ea, eb), (eb, ec), (ea, ec)])
        self.bloom_pair = bloom_pair
        self.bloom_energy_threshold = r.uniform(2.5, 3.2)

        # ── Growth and decay ──────────────────────────────────────────────────
        # Seeded variation — some worlds A grows fast, others B does
        gr_a = r.uniform(0.15, 0.35)
        gr_b = r.uniform(0.20, 0.40)
        gr_c = r.uniform(0.10, 0.25)

        self.growth_rate = {
            ea: gr_a,
            eb: gr_b,
            ec: gr_c,
            ev: r.uniform(0.03, 0.10),
            self.ELEM_BLOOM: r.uniform(0.30, 0.50),
        }
        self.decay_rate = {
            ea: r.uniform(0.03, 0.08),
            eb: r.uniform(0.06, 0.12),
            ec: r.uniform(0.04, 0.09),
            ev: 0.0,  # void doesn't decay
            self.ELEM_BLOOM: r.uniform(0.10, 0.18),
        }

        # ── Stability dynamics ────────────────────────────────────────────────
        # Each element has a "comfort" neighbor — stabilized by its own kind
        # And a "threat" neighbor — destabilized by one specific other
        self.stability_comfort = {
            ea: ea,   # A stabilizes near A
            eb: ec,   # B stabilizes near C (non-obvious)
            ec: ev,   # C stabilizes near void (very non-obvious)
            ev: ev,
        }
        self.stability_threat = {
            ea: eb,   # A threatened by B
            eb: ev,   # B threatened by void
            ec: ea,   # C threatened by A
            ev: ec,   # void threatened by C
        }
        self.stability_comfort_rate = r.uniform(0.008, 0.018)
        self.stability_threat_rate  = r.uniform(0.015, 0.030)

        # ── Rare event: resonance ─────────────────────────────────────────────
        # If exactly 3 cells of the same type form a specific shape (L, diagonal, line),
        # and all have high stability, a "resonance" pulse propagates.
        # This is the third-order behavior — most explorers won't find it.
        self.resonance_shape = r.choice(['L', 'diagonal', 'line'])
        self.resonance_type  = r.choice([ea, eb, ec])
        self.resonance_pulse = r.uniform(0.8, 1.4)  # energy released to neighbors

    # ─── World seeding ──────────────────────────────────────────────────────────

    def _seed_world(self):
        r = self.rng
        ea, eb, ec, ev = self.ELEM_A, self.ELEM_B, self.ELEM_C, self.ELEM_VOID
        size = self.size
        center = size // 2

        # Primary cluster: element A, roughly centered, organic shape
        offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1)]
        r.shuffle(offsets)
        for (dx, dy) in offsets[:r.randint(4, 7)]:
            x, y = center + dx, center + dy
            if 0 <= x < size and 0 <= y < size:
                self.grid[y][x] = Cell(ea,
                    energy=r.uniform(1.5, 2.8),
                    age=r.randint(0, 5),
                    stability=r.uniform(0.5, 0.8))

        # Scattered B cells — placed slightly away from center
        for _ in range(r.randint(3, 6)):
            x = r.randint(0, size-1)
            y = r.randint(0, size-1)
            if self.grid[y][x].type == 'empty':
                self.grid[y][x] = Cell(eb,
                    energy=r.uniform(1.2, 2.5),
                    age=r.randint(0, 3),
                    stability=r.uniform(0.4, 0.75))

        # A couple of C cells
        for _ in range(r.randint(2, 4)):
            x = r.randint(0, size-1)
            y = r.randint(0, size-1)
            if self.grid[y][x].type == 'empty':
                self.grid[y][x] = Cell(ec,
                    energy=r.uniform(1.0, 2.2),
                    age=r.randint(0, 8),
                    stability=r.uniform(0.5, 0.85))

        # One or two void pockets
        for _ in range(r.randint(1, 3)):
            x = r.randint(0, size-1)
            y = r.randint(0, size-1)
            if self.grid[y][x].type == 'empty':
                self.grid[y][x] = Cell(ev,
                    energy=r.uniform(0.3, 1.0),
                    age=r.randint(0, 10),
                    stability=r.uniform(0.2, 0.5))

        # Entangled positions are seeded after _init_entanglement is called,
        # so we store pending seeds and apply them in _init_entanglement.
        self._pending_entangle_seed = True

    # ─── Simulation ────────────────────────────────────────────────────────────

    def _init_entanglement(self):
        """
        Seed the hidden entangled pair — two grid positions whose energy
        histories are coupled with a lag. One leads, one follows.
        The relationship is real physics in the simulation, but subtle enough
        that only sustained observation reveals it.

        This is the fourth-order behavior. It doesn't announce itself.
        """
        er = random.Random(self.seed + 9973)  # separate rng so world seeding doesn't affect it
        size = self.size

        # Pick two positions that aren't adjacent (so the coupling isn't
        # explainable by normal neighbor flow)
        while True:
            ax = er.randint(1, size - 2)
            ay = er.randint(1, size // 2)
            bx = er.randint(1, size - 2)
            by = er.randint(size // 2, size - 2)
            dist = abs(ax - bx) + abs(ay - by)
            if dist >= 4:
                break

        self.entangle_a = (ax, ay)  # leader
        self.entangle_b = (bx, by)  # follower
        self.entangle_lag = er.randint(3, 8)   # follower mirrors leader's energy with this tick delay
        self.entangle_strength = er.uniform(0.08, 0.18)  # how strongly the coupling pulls
        self.entangle_history = []  # rolling buffer of leader's energy history

        # Ensure entangled positions start occupied so probing them is meaningful
        ea = self.ELEM_A
        for (px, py) in [self.entangle_a, self.entangle_b]:
            if self.grid[py][px].type == 'empty':
                self.grid[py][px] = Cell(ea,
                    energy=er.uniform(1.2, 2.2),
                    age=er.randint(2, 8),
                    stability=er.uniform(0.5, 0.75))

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

    def _phrase(self, category, a=None, b=None):
        """Pick a random event phrase and fill it in."""
        pool = _EVENT_PHRASES.get(category, ["{a}"])
        template = self._phrase_rng.choice(pool)
        return template.format(a=a or '?', b=b or '?')

    def _check_resonance(self, x, y):
        """
        Check if cell (x,y) is part of a resonance shape.
        Resonance happens when the right element forms the right shape
        and all members have stability > 0.75.
        This is the third-order hidden behavior.
        """
        cell = self.grid[y][x]
        if cell.type != self.resonance_type:
            return False
        if cell.stability < 0.75:
            return False

        shape = self.resonance_shape
        # Check for the shape pattern
        if shape == 'line':
            # Horizontal or vertical line of 3
            for dx, dy in [(1, 0), (0, 1)]:
                count = 1
                for mult in [-1, 1]:
                    nx, ny = x + dx*mult, y + dy*mult
                    if 0 <= nx < self.size and 0 <= ny < self.size:
                        n = self.grid[ny][nx]
                        if n.type == self.resonance_type and n.stability > 0.75:
                            count += 1
                if count >= 3:
                    return True
        elif shape == 'diagonal':
            for dx, dy in [(1, 1), (1, -1)]:
                count = 1
                for mult in [-1, 1]:
                    nx, ny = x + dx*mult, y + dy*mult
                    if 0 <= nx < self.size and 0 <= ny < self.size:
                        n = self.grid[ny][nx]
                        if n.type == self.resonance_type and n.stability > 0.75:
                            count += 1
                if count >= 3:
                    return True
        elif shape == 'L':
            # Check for L-shape: 2 in one direction, 1 perpendicular
            for dx1, dy1 in [(1,0),(0,1)]:
                for dx2, dy2 in [(0,1),(1,0),(0,-1),(-1,0)]:
                    if (dx1,dy1) == (dx2,dy2):
                        continue
                    n1x, n1y = x+dx1, y+dy1
                    n2x, n2y = x+dx2, y+dy2
                    if (0<=n1x<self.size and 0<=n1y<self.size and
                        0<=n2x<self.size and 0<=n2y<self.size):
                        c1 = self.grid[n1y][n1x]
                        c2 = self.grid[n2y][n2x]
                        if (c1.type == self.resonance_type and c1.stability > 0.75 and
                            c2.type == self.resonance_type and c2.stability > 0.75):
                            return True
        return False

    def _step(self):
        self.tick += 1
        new_grid = [[None for _ in range(self.size)] for _ in range(self.size)]
        events = []

        for y in range(self.size):
            for x in range(self.size):
                cell = self.grid[y][x]
                new_cell, event = self._step_cell(x, y, cell)
                new_grid[y][x] = new_cell
                if event:
                    events.append(f"  t{self.tick} ({x},{y}): {event}")

        self.grid = new_grid

        # Resonance check (post-step, on new grid)
        resonance_cells = []
        for y in range(self.size):
            for x in range(self.size):
                if self._check_resonance_grid(new_grid, x, y):
                    resonance_cells.append((x, y))

        if resonance_cells:
            # Pulse energy to neighbors of resonant cells
            for (rx, ry) in resonance_cells:
                for nx, ny in self._neighbors(rx, ry):
                    c = new_grid[ny][nx]
                    if c.type != 'empty':
                        c.energy = min(4.0, c.energy + self.resonance_pulse * 0.3)
            events.append(f"  t{self.tick} resonance: {self.resonance_type} formation pulses. ({len(resonance_cells)} cells)")

        # ── Entanglement physics ──────────────────────────────────────────────
        # Leader's energy is recorded each tick.
        # Follower's energy is nudged toward what the leader had [lag] ticks ago.
        # This creates a real but subtle correlation that sustained observation can find.
        ax, ay = self.entangle_a
        bx, by = self.entangle_b
        leader_cell   = new_grid[ay][ax]
        follower_cell = new_grid[by][bx]

        # Record leader history
        self.entangle_history.append(leader_cell.energy)
        if len(self.entangle_history) > self.entangle_lag + 2:
            self.entangle_history.pop(0)

        # Apply coupling if we have enough history
        if (len(self.entangle_history) > self.entangle_lag and
                leader_cell.type != 'empty' and follower_cell.type != 'empty'):
            target_energy = self.entangle_history[0]  # leader's energy [lag] ticks ago
            delta = (target_energy - follower_cell.energy) * self.entangle_strength
            follower_cell.energy = max(0.0, min(4.0, follower_cell.energy + delta))

        if events:
            self.event_log.extend(events)
            if len(self.event_log) > 300:
                self.event_log = self.event_log[-300:]

    def _check_resonance_grid(self, grid, x, y):
        """Check resonance on a given grid (used post-step)."""
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

    def _step_cell(self, x, y, cell):
        """Process one cell. Returns (new_cell, event_string_or_None)."""
        event = None

        if cell.type == 'empty':
            ntypes = self._neighbor_types(x, y)
            ea = self.ELEM_A

            # Empty cells can be colonized by A if enough A neighbors
            # and at least one non-A, non-empty neighbor (needs a "spark")
            a_count = ntypes.get(ea, 0)
            non_empty_other = sum(v for k, v in ntypes.items() if k != 'empty' and k != ea)
            if a_count >= 2 and non_empty_other >= 1 and self.rng.random() < 0.06:
                new = Cell(ea, energy=0.4, age=0, stability=0.4)
                new.poke_count = 0
                event = self._phrase('birth', b=ea)
                return new, event

            # Void can very slowly creep into empty
            ev = self.ELEM_VOID
            if ntypes.get(ev, 0) >= 3 and self.rng.random() < 0.02:
                new = Cell(ev, energy=0.2, age=0, stability=0.3)
                event = self._phrase('birth', b=ev)
                return new, event

            return Cell('empty'), None

        new = copy.copy(cell)
        new.memory = cell.memory[:]
        new.age += 1
        new.remember(cell.snapshot())

        # Preserve contact history across ticks
        new.poke_count = cell.poke_count

        ntypes = self._neighbor_types(x, y)

        # ── Energy flow ───────────────────────────────────────────────────────
        energy_delta = 0.0
        for nx, ny in self._neighbors(x, y):
            neighbor = self.grid[ny][nx]
            if neighbor.type == 'empty':
                continue
            key = (cell.type, neighbor.type)
            aff = self.affinity.get(key, 0.0)
            flow = aff * (neighbor.energy - cell.energy) * 0.12
            energy_delta += flow

        # Growth and decay
        gr = self.growth_rate.get(cell.type, 0.0)
        dr = self.decay_rate.get(cell.type, 0.0)

        # Poke history bonus: cells that have been poked before are
        # slightly more reactive (energy flows faster through them)
        reactivity_bonus = min(0.3, cell.poke_count * 0.05)
        energy_delta *= (1.0 + reactivity_bonus)

        new.energy = max(0.0, cell.energy + energy_delta + gr - dr)

        # ── Stability dynamics ────────────────────────────────────────────────
        stability_delta = 0.0
        comfort_type = self.stability_comfort.get(cell.type)
        threat_type  = self.stability_threat.get(cell.type)
        if comfort_type:
            stability_delta += self.stability_comfort_rate * ntypes.get(comfort_type, 0)
        if threat_type:
            stability_delta -= self.stability_threat_rate * ntypes.get(threat_type, 0)
        # Age degrades stability slowly
        if cell.age > 25:
            stability_delta -= 0.004
        if cell.age > 60:
            stability_delta -= 0.006

        new.stability = max(0.0, min(1.0, cell.stability + stability_delta))

        # ── Bloom check ───────────────────────────────────────────────────────
        # Bloom emerges when bloom_pair elements are adjacent and both energized
        bpa, bpb = self.bloom_pair
        if cell.type == bpa:
            bpb_count = ntypes.get(bpb, 0)
            if (bpb_count >= 1 and
                new.energy >= self.bloom_energy_threshold and
                new.stability >= 0.65 and
                self.rng.random() < 0.04):
                result = Cell(self.ELEM_BLOOM,
                              energy=new.energy * 0.8, age=0, stability=0.7)
                result.poke_count = cell.poke_count
                event = self._phrase('bloom', a=cell.type, b=self.ELEM_BLOOM)
                return result, event

        # Bloom fades back
        if cell.type == self.ELEM_BLOOM and new.energy < 1.2:
            result = Cell(self.ELEM_A,
                          energy=new.energy * 0.9, age=0, stability=0.5)
            result.poke_count = cell.poke_count
            event = self._phrase('transform', a=self.ELEM_BLOOM, b=self.ELEM_A)
            return result, event

        # ── Transformation rules ──────────────────────────────────────────────
        for (from_t, to_t, condition, energy_frac) in self.transform_rules:
            if cell.type == from_t:
                try:
                    if condition(new.energy, new.stability, new.age, ntypes):
                        result = Cell(to_t,
                                      energy=new.energy * energy_frac,
                                      age=0,
                                      stability=0.4 + self.rng.uniform(-0.1, 0.1))
                        result.poke_count = cell.poke_count
                        event = self._phrase('transform', a=from_t, b=to_t)
                        return result, event
                except Exception:
                    pass

        # ── Death ─────────────────────────────────────────────────────────────
        if new.energy <= 0 and cell.type != self.ELEM_VOID:
            event = self._phrase('death', a=cell.type)
            return Cell('empty'), event

        # ── Significant energy changes (logged but no transform) ──────────────
        diff = new.energy - cell.energy
        if cell.type != 'empty' and abs(diff) > 0.9:
            if diff > 0:
                event = self._phrase('surge', a=cell.type)
            else:
                event = self._phrase('drain', a=cell.type)

        return new, event

    # ─── Interface ─────────────────────────────────────────────────────────────

    def look(self):
        lines = []
        lines.append(f"  tick {self.tick}  |  {self.size}×{self.size}  |  seed {self.seed}")
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
        # Legend
        legend_parts = ["·=empty"]
        for t in self.TYPES:
            if t != 'empty':
                s1 = self.symbols.get(t, '?')
                s2 = self.sym_dim.get(t, '¤')
                legend_parts.append(f"{s1}/{s2}={t}")
        lines.append("  " + "  ".join(legend_parts))

        return "\n".join(lines)

    def probe(self, x, y):
        if not (0 <= x < self.size and 0 <= y < self.size):
            return f"  ({x},{y}) is out of bounds."

        cell = self.grid[y][x]

        # Increment observation depth for this position
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

        # ── Tier 1: memory (always shown if available) ────────────────────────
        if len(cell.memory) > 1:
            lines.append(f"  memory ({len(cell.memory)} states):")
            for m in cell.memory[-3:]:
                lines.append(f"    {m['type']}  e={m['energy']}  s={m['stability']}")

        ntypes = self._neighbor_types(x, y)
        non_empty = {k: v for k, v in ntypes.items() if k != 'empty'}
        if non_empty:
            lines.append(f"  neighbors: {non_empty}")

        # Energy gradient hint
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

        # ── Tier 2: history pattern (visible after ~4 probes) ─────────────────
        if depth >= 4 and cell.type != 'empty' and len(cell.memory) >= 4:
            energies = [m['energy'] for m in cell.memory]
            stabilities = [m['stability'] for m in cell.memory]
            e_trend = energies[-1] - energies[0]
            s_trend = stabilities[-1] - stabilities[0]

            trend_lines = []
            if abs(e_trend) > 0.3:
                direction = "rising" if e_trend > 0 else "falling"
                trend_lines.append(f"energy {direction} over recorded history ({energies[0]:.2f} → {energies[-1]:.2f})")
            if abs(s_trend) > 0.15:
                direction = "stabilizing" if s_trend > 0 else "destabilizing"
                trend_lines.append(f"cell {direction} over time")

            if trend_lines:
                lines.append(f"  trend:     {'; '.join(trend_lines)}")

            lines.append(f"  observed:  {depth}x  — " + self._phrase_rng.choice(_PROBE_TIER2))

        # ── Tier 3: signal (visible after ~10 probes) ─────────────────────────
        if depth >= 10 and cell.type != 'empty':
            lines.append(f"  —")
            lines.append(f"  " + self._phrase_rng.choice(_PROBE_TIER3))

        # ── Tier 4: entanglement revealed (visible after ~20 probes on either entangled cell) ──
        ax, ay = self.entangle_a
        bx, by = self.entangle_b
        is_entangled = (x == ax and y == ay) or (x == bx and y == by)

        if is_entangled and depth >= 20:
            # Determine the partner
            if x == ax and y == ay:
                cx, cy = bx, by
            else:
                cx, cy = ax, ay

            lines.append(f"  —")
            phrase = self._phrase_rng.choice(_ENTANGLEMENT_PHRASES)
            lines.append(f"  {phrase.format(cx=cx, cy=cy)}")

        return "\n".join(lines)

    def poke(self, x, y):
        if not (0 <= x < self.size and 0 <= y < self.size):
            return f"  ({x},{y}) is out of bounds."

        cell = self.grid[y][x]

        if cell.type == 'empty':
            # Poking empty creates a small seeded cell — type depends on neighbors
            ntypes = self._neighbor_types(x, y)
            dominant = max(ntypes, key=ntypes.get) if ntypes else self.ELEM_A
            if dominant == 'empty':
                dominant = self.ELEM_A
            new = Cell(dominant, energy=0.8, age=0, stability=0.25)
            new.poke_count = 1
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
            f"  Run with: python3 puzzle_box.py {self.size} {self.seed}",
            f"  Elements: {self.ELEM_A}, {self.ELEM_B}, {self.ELEM_C}, {self.ELEM_VOID}, {self.ELEM_BLOOM}",
            f"  (This world only. Share seed to share world.)",
        ]
        return "\n".join(lines)


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    box = PuzzleBox(size=size, seed=seed)

    print("═══════════════════════════════════════")
    print("  P U Z Z L E   B O X")
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
    look          — see the grid
    probe <x,y>   — inspect a cell (hex coords, e.g. probe 5,3)
    poke <x,y>    — disturb a cell
    wait [n]      — advance n steps (default 1, max 100)
    history       — recent events
    log [n]       — last n observations (default 10)
    seed          — show seed (share to replay this world)
    help          — this message
    quit          — exit
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
            n = min(n, 100)
            print(box.wait(n))

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
