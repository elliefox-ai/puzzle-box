#!/usr/bin/env python3
"""
puzzle_box.py — A micro-world with hidden rules.

A simulated grid world with emergent behavior.
The rules aren't documented. Discover them by exploring.

Usage:
    python3 puzzle_box.py [grid_size]

Commands:
    look          — see the current grid
    probe <x,y>   — inspect a cell in detail
    poke <x,y>    — disturb a cell
    wait [n]      — advance n steps (default 1)
    history       — recent significant events
    log [n]       — show last n observations (default 10)
    help          — show commands
    quit          — exit
"""

import random
import sys
import copy
import json
from collections import defaultdict

# ─── Hidden Rule Parameters (the designer doesn't show these) ───

# Element types and their base properties
# Interactions are emergent from the rules, not defined directly

SEED = None  # Set to int for reproducibility

class Cell:
    __slots__ = ['type', 'energy', 'age', 'stability', 'memory']
    
    def __init__(self, type='empty', energy=0.0, age=0, stability=1.0):
        self.type = type
        self.energy = energy
        self.age = age
        self.stability = stability
        self.memory = []  # remembers last few states
    
    def snapshot(self):
        return {
            'type': self.type,
            'energy': round(self.energy, 2),
            'age': self.age,
            'stability': round(self.stability, 2)
        }

    def remember(self, state):
        self.memory.append(state)
        if len(self.memory) > 5:
            self.memory.pop(0)


class PuzzleBox:
    # Element types with hidden affinities
    TYPES = ['empty', 'flora', 'crystal', 'ember', 'void', 'bloom']
    
    def __init__(self, size=12, seed=None):
        self.size = size
        self.rng = random.Random(seed)
        self.tick = 0
        self.grid = [[Cell() for _ in range(size)] for _ in range(size)]
        self.event_log = []
        self.observations = []
        
        # Hidden rule parameters — these create the emergent behavior
        self._init_rules()
        self._seed_world()
    
    def _init_rules(self):
        """Initialize hidden interaction parameters."""
        # Energy affinity matrix — how much energy flows between type pairs
        # Positive = attracts/feeds, Negative = repels/drains
        self.affinity = {
            ('flora', 'crystal'): 0.4,
            ('crystal', 'ember'): -0.5,
            ('ember', 'flora'): 0.6,
            ('flora', 'void'): -0.7,
            ('void', 'crystal'): 0.3,
            ('crystal', 'flora'): 0.2,
            ('ember', 'void'): 0.4,
            ('void', 'ember'): -0.3,
            ('bloom', 'flora'): 1.0,
            ('bloom', 'crystal'): 0.7,
            ('bloom', 'ember'): -0.4,
            ('bloom', 'void'): -0.6,
            ('flora', 'ember'): 0.3,
            ('ember', 'crystal'): 0.1,
        }
        
        # Transformation thresholds
        self.transform = {
            ('flora', 'crystal'): lambda e, s: e > 2.0 and s < 0.4,    # stressed flora crystallizes
            ('crystal', 'ember'): lambda e, s: e > 2.5 and s > 0.7,    # saturated crystal ignites
            ('ember', 'void'): lambda e, s: e < 0.8 and s < 0.3,       # depleted ember collapses
            ('void', 'flora'): lambda e, s: 0.2 < e < 1.0 and s > 0.5, # calm void sprouts
            ('flora', 'bloom'): lambda e, s: e > 3.0 and s > 0.8,       # thriving flora blooms
            ('crystal', 'bloom'): lambda e, s: e > 2.8 and self.tick % 7 == 0,  # crystal blooms on a cycle
            ('ember', 'bloom'): lambda e, s: e < 0.5 and self.age_neighbors_have('void', 2),
            ('bloom', 'flora'): lambda e, s: e < 1.5,                    # bloom fades to flora
        }
        
        # Growth parameters
        self.growth_rate = {
            'flora': 0.25,
            'crystal': 0.12,
            'ember': 0.30,
            'void': 0.08,
            'bloom': 0.40,
        }
        
        # Decay parameters
        self.decay_rate = {
            'flora': 0.05,
            'crystal': 0.02,
            'ember': 0.08,
            'void': 0.00,
            'bloom': 0.12,
        }
    
    def age_neighbors_have(self, type_name, count):
        """Check if neighbors of a type exist (used in transform rules)."""
        # This is a stub — actual check happens in _step_cell
        return False
    
    def _seed_world(self):
        """Place initial elements with some structure."""
        center = self.size // 2
        # Cluster of flora in one region
        for x, y in [(center-2, center-1), (center-1, center), (center, center), (center+1, center), (center-1, center+1), (center, center+1)]:
            if 0 <= x < self.size and 0 <= y < self.size:
                self.grid[y][x] = Cell('flora', energy=self.rng.uniform(1.5, 3.0), age=0, stability=self.rng.uniform(0.5, 0.8))
        
        # Scattered crystals
        for _ in range(5):
            x, y = self.rng.randint(0, self.size-1), self.rng.randint(0, self.size-1)
            self.grid[y][x] = Cell('crystal', energy=self.rng.uniform(1.5, 3.5), age=0, stability=self.rng.uniform(0.6, 0.9))
        
        # A couple of embers
        for _ in range(2):
            x, y = self.rng.randint(0, self.size-1), self.rng.randint(0, self.size-1)
            self.grid[y][x] = Cell('ember', energy=self.rng.uniform(2.0, 3.5), age=0, stability=self.rng.uniform(0.4, 0.7))
        
        # A void pocket or two
        for _ in range(2):
            x, y = self.rng.randint(0, self.size-1), self.rng.randint(0, self.size-1)
            self.grid[y][x] = Cell('void', energy=self.rng.uniform(0.5, 1.5), age=0, stability=self.rng.uniform(0.3, 0.5))
    
    def _neighbors(self, x, y):
        """Get valid neighbor coordinates (8-connected)."""
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
        """Count neighbor types."""
        counts = defaultdict(int)
        for nx, ny in self._neighbors(x, y):
            counts[self.grid[ny][nx].type] += 1
        return counts
    
    def _step(self):
        """Advance the simulation one tick."""
        self.tick += 1
        new_grid = [[None for _ in range(self.size)] for _ in range(self.size)]
        events = []
        
        for y in range(self.size):
            for x in range(self.size):
                cell = self.grid[y][x]
                new_cell = self._step_cell(x, y, cell)
                new_grid[y][x] = new_cell
                
                # Log transformations
                if new_cell.type != cell.type:
                    events.append(f"  t{self.tick} ({x},{y}): {cell.type} → {new_cell.type}")
                
                # Log significant energy changes
                if cell.type != 'empty' and abs(new_cell.energy - cell.energy) > 1.0:
                    direction = "surge" if new_cell.energy > cell.energy else "drain"
                    events.append(f"  t{self.tick} ({x},{y}): {cell.type} {direction} ({cell.energy:.1f} → {new_cell.energy:.1f})")
        
        self.grid = new_grid
        if events:
            self.event_log.extend(events)
            if len(self.event_log) > 200:
                self.event_log = self.event_log[-200:]
    
    def _step_cell(self, x, y, cell):
        """Process one cell for one tick."""
        new = copy.deepcopy(cell)
        new.age += 1
        new.remember(cell.snapshot())
        
        if cell.type == 'empty':
            # Empty cells can spontaneously generate if neighbors are right
            ntypes = self._neighbor_types(x, y)
            if ntypes.get('flora', 0) >= 2 and ntypes.get('crystal', 0) >= 1:
                if self.rng.random() < 0.08:
                    new = Cell('flora', energy=0.5, age=0, stability=0.5)
                    return new
            # Void can spread into empty
            if ntypes.get('void', 0) >= 2 and self.rng.random() < 0.03:
                new = Cell('void', energy=0.3, age=0, stability=0.3)
                return new
            return new
        
        # Energy flow from neighbors
        energy_delta = 0.0
        ntypes = self._neighbor_types(x, y)
        
        for nx, ny in self._neighbors(x, y):
            neighbor = self.grid[ny][nx]
            if neighbor.type == 'empty':
                continue
            key = (cell.type, neighbor.type)
            aff = self.affinity.get(key, 0.0)
            # Energy flows proportional to difference
            flow = aff * (neighbor.energy - cell.energy) * 0.1
            energy_delta += flow
        
        # Growth and decay
        gr = self.growth_rate.get(cell.type, 0.0)
        dr = self.decay_rate.get(cell.type, 0.0)
        
        # Stability dynamics — influenced by neighbors and age
        stability_delta = 0.0
        if cell.type == 'crystal':
            stability_delta += 0.01 * ntypes.get('crystal', 0)  # crystals stabilize each other
        if cell.type == 'flora':
            stability_delta -= 0.02 * ntypes.get('ember', 0)    # ember destabilizes flora
            stability_delta += 0.01 * ntypes.get('flora', 0)    # flora stabilizes in groups
        if cell.type == 'ember':
            stability_delta -= 0.03 * ntypes.get('void', 0)     # void destabilizes ember
        if cell.type == 'void':
            stability_delta += 0.02 * ntypes.get('void', 0)     # void stabilizes in clusters
        if cell.type == 'bloom':
            stability_delta += 0.01  # bloom slowly stabilizes itself
        
        # Age effect on stability
        if cell.age > 20:
            stability_delta -= 0.005
        if cell.age > 50:
            stability_delta -= 0.01
        
        new.stability = max(0.0, min(1.0, cell.stability + stability_delta))
        new.energy = max(0.0, cell.energy + energy_delta + gr - dr)
        
        # Check transformations
        for (from_type, to_type), condition in self.transform.items():
            if cell.type == from_type:
                try:
                    # Special case for ember→bloom (needs void neighbors)
                    if (from_type, to_type) == ('ember', 'bloom'):
                        if ntypes.get('void', 0) >= 2 and cell.energy < 0.3:
                            new = Cell(to_type, energy=2.0, age=0, stability=0.7)
                            return new
                    elif condition(new.energy, new.stability):
                        new = Cell(to_type, energy=new.energy * 0.7, age=0, stability=0.5)
                        return new
                except:
                    pass
        
        # Bloom is special — it radiates energy to neighbors and creates life
        if cell.type == 'bloom':
            if cell.energy > 2.0 and self.rng.random() < 0.1:
                # Try to seed a neighbor
                empty_neighbors = [(nx, ny) for nx, ny in self._neighbors(x, y) if self.grid[ny][nx].type == 'empty']
                if empty_neighbors:
                    sx, sy = self.rng.choice(empty_neighbors)
                    # Don't modify new_grid here — we'll handle it next tick
                    new.energy -= 0.5
        
        # Death condition
        if new.energy <= 0 and cell.type not in ('void',):
            new = Cell('empty', energy=0.0, age=0, stability=1.0)
        
        return new
    
    def look(self):
        """Render the grid as text."""
        lines = []
        lines.append(f"  tick {self.tick}  |  grid {self.size}×{self.size}")
        lines.append("")
        
        # Column headers
        header = "    " + "".join(f"{x:2d}" for x in range(self.size))
        lines.append(header)
        
        symbols = {
            'empty': '·',
            'flora': '♣',
            'crystal': '◆',
            'ember': '▲',
            'void': '○',
            'bloom': '✿',
        }
        
        for y in range(self.size):
            row = f" {y:2d} "
            for x in range(self.size):
                cell = self.grid[y][x]
                sym = symbols.get(cell.type, '?')
                # Intensity based on energy
                if cell.type == 'empty':
                    row += " ·"
                elif cell.energy > 3.0:
                    row += sym  # Will show as full symbol
                elif cell.energy > 1.5:
                    row += sym.lower() if sym.isalpha() else sym
                else:
                    row += "·"
            
            # Actually let me redo this more readably
            pass
        
        # Redo with better rendering
        lines = []
        lines.append(f"  tick {self.tick}  |  grid {self.size}×{self.size}")
        
        # Count types
        type_counts = defaultdict(int)
        for y in range(self.size):
            for x in range(self.size):
                type_counts[self.grid[y][x].type] += 1
        
        summary = "  ".join(f"{symbols.get(t, '?')}{c}" for t, c in sorted(type_counts.items()) if t != 'empty')
        lines.append(f"  {summary}")
        lines.append("")
        
        header = "    " + "".join(f" {x:x}" for x in range(self.size))
        lines.append(header)
        
        for y in range(self.size):
            row = f"  {y:x} "
            for x in range(self.size):
                cell = self.grid[y][x]
                if cell.type == 'empty':
                    row += " ·"
                elif cell.type == 'bloom':
                    row += " ✿"
                elif cell.type == 'flora':
                    if cell.energy > 3.0:
                        row += " ♣"
                    elif cell.energy > 1.0:
                        row += " ♠"
                    else:
                        row += " ¤"
                elif cell.type == 'crystal':
                    if cell.energy > 3.0:
                        row += " ◆"
                    elif cell.energy > 1.0:
                        row += " ◇"
                    else:
                        row += " ¤"
                elif cell.type == 'ember':
                    if cell.energy > 3.0:
                        row += " ▲"
                    elif cell.energy > 1.0:
                        row += " △"
                    else:
                        row += " ¤"
                elif cell.type == 'void':
                    if cell.energy > 1.0:
                        row += " ○"
                    else:
                        row += " ◦"
                else:
                    row += " ?"
            lines.append(row)
        
        lines.append("")
        lines.append("  Symbols: · empty | ♣♠¤ flora | ◆◇ crystal | ▲△ ember | ○◦ void | ✿ bloom")
        
        return "\n".join(lines)
    
    def probe(self, x, y):
        """Inspect a cell in detail."""
        if not (0 <= x < self.size and 0 <= y < self.size):
            return f"  ({x},{y}) is out of bounds."
        
        cell = self.grid[y][x]
        lines = []
        lines.append(f"  Cell ({x},{y}) at tick {self.tick}")
        lines.append(f"  Type:      {cell.type}")
        lines.append(f"  Energy:    {cell.energy:.2f}")
        lines.append(f"  Age:       {cell.age}")
        lines.append(f"  Stability: {cell.stability:.2f}")
        
        if cell.memory:
            lines.append(f"  History (last {len(cell.memory)}):")
            for i, m in enumerate(cell.memory[-3:]):
                lines.append(f"    {i+1}. {m['type']} e={m['energy']} s={m['stability']}")
        
        # Neighbor info (what you can sense)
        ntypes = self._neighbor_types(x, y)
        if ntypes:
            lines.append(f"  Nearby: {dict(ntypes)}")
        
        # Energy gradient hint
        total_e = sum(self.grid[ny][nx].energy for nx, ny in self._neighbors(x, y) if self.grid[ny][nx].type != 'empty')
        if cell.type != 'empty':
            if total_e > cell.energy * 4:
                lines.append(f"  Energy feels like it's flowing in.")
            elif total_e < cell.energy:
                lines.append(f"  Energy feels like it's draining.")
        
        return "\n".join(lines)
    
    def poke(self, x, y):
        """Disturb a cell — inject energy and reduce stability."""
        if not (0 <= x < self.size and 0 <= y < self.size):
            return f"  ({x},{y}) is out of bounds."
        
        cell = self.grid[y][x]
        
        if cell.type == 'empty':
            # Poking empty space creates a spark — small ember
            self.grid[y][x] = Cell('ember', energy=1.0, age=0, stability=0.3)
            obs = f"  Poked ({x},{y}). A spark flickers."
        else:
            # Inject energy and destabilize
            cell.energy += 1.5
            cell.stability = max(0.0, cell.stability - 0.3)
            obs = f"  Poked ({x},{y}). {cell.type} destabilizes (energy {cell.energy:.1f}, stability {cell.stability:.2f})."
        
        self.observations.append(f"t{self.tick}: {obs}")
        if len(self.observations) > 100:
            self.observations = self.observations[-100:]
        
        return obs
    
    def wait(self, steps=1):
        """Advance the simulation."""
        events_before = len(self.event_log)
        for _ in range(steps):
            self._step()
        new_events = self.event_log[events_before:]
        
        lines = [f"  Advanced {steps} tick(s). Now at tick {self.tick}."]
        if new_events:
            lines.append(f"  Events ({len(new_events)}):")
            for e in new_events[:20]:
                lines.append(e)
            if len(new_events) > 20:
                lines.append(f"  ... and {len(new_events) - 20} more.")
        else:
            lines.append("  Nothing notable happened.")
        
        obs = f"t{self.tick}: waited {steps} ticks"
        if new_events:
            obs += f", {len(new_events)} events"
        self.observations.append(obs)
        
        return "\n".join(lines)
    
    def history(self):
        """Show recent significant events."""
        if not self.event_log:
            return "  No events recorded yet."
        
        lines = ["  Recent events:"]
        for e in self.event_log[-20:]:
            lines.append(e)
        return "\n".join(lines)
    
    def show_log(self, n=10):
        """Show observation log."""
        if not self.observations:
            return "  No observations yet. Try looking around."
        
        lines = ["  Observation log:"]
        for obs in self.observations[-n:]:
            lines.append(f"  {obs}")
        return "\n".join(lines)


def main():
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    seed = SEED or random.randint(0, 99999)
    box = PuzzleBox(size=size, seed=seed)
    
    print("═══════════════════════════════════════")
    print("  P U Z Z L E   B O X")
    print("═══════════════════════════════════════")
    print()
    print(f"  A {size}×{size} world, waiting.")
    print("  The rules are not documented.")
    print("  Type 'help' for commands.")
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
        
        if verb == 'quit' or verb == 'exit':
            print("  Box closed.")
            break
        
        elif verb == 'help':
            print("""
  Commands:
    look          — see the grid
    probe <x,y>   — inspect a cell
    poke <x,y>    — disturb a cell
    wait [n]      — advance n steps (default 1)
    history       — recent significant events
    log [n]       — last n observations
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
                    print("  Usage: probe <x,y>  (e.g. probe 5,3)")
        
        elif verb == 'poke':
            if len(parts) < 2:
                print("  Usage: poke <x,y>")
            else:
                try:
                    coords = parts[1].split(',')
                    x, y = int(coords[0], 16), int(coords[1], 16)
                    print(box.poke(x, y))
                except (ValueError, IndexError):
                    print("  Usage: poke <x,y>  (e.g. poke 5,3)")
        
        elif verb == 'wait':
            n = 1
            if len(parts) > 1:
                try:
                    n = int(parts[1])
                except ValueError:
                    print("  Usage: wait [n]")
                    continue
            if n > 50:
                n = 50
                print("  (Capped at 50)")
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
        
        else:
            print(f"  Unknown command: {verb}. Type 'help' for commands.")


if __name__ == '__main__':
    main()
