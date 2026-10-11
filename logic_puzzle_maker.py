#!/usr/bin/env python3
"""
Logic Puzzle Maker Pro - A PySide6 Desktop Application
Create, edit, solve, and export multiple types of logic puzzles.

Puzzle Types:
  1. Logic Grid  - category-based deduction
  2. Nonogram    - picture logic (fill cells by row/column clues)
  3. Word Logic  - Einstein riddle / constraint-based deduction
  4. Kakuro      - cross-sum number placement puzzle
  5. Word Search - find hidden words in a letter grid

Features:
  - Multi-tab workspace, undo/redo, solve timer, hint system
  - Auto-generate puzzles, difficulty scoring, dark/light theme
  - Save/load (.lpuzzle), HTML export, progress tracking, statistics
  - Logic Grid solver engine, auto-clue generation, pencil marks
"""

import sys, json, random, time, copy, re
from pathlib import Path
from typing import Optional
from collections import defaultdict
from itertools import permutations

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QDialog, QFileDialog,
    QMessageBox, QTabWidget, QSplitter, QGroupBox, QFormLayout,
    QSpinBox, QScrollArea, QSizePolicy, QToolBar, QStatusBar,
    QMenu, QMenuBar, QAction, QAbstractItemView, QHeaderView,
    QTableWidget, QTableWidgetItem, QCheckBox, QRadioButton,
    QButtonGroup, QFrame, QStackedWidget, QProgressBar,
)
from PySide6.QtCore import (
    Qt, QSize, Signal, QTimer, QElapsedTimer, QMimeData
)
from PySide6.QtGui import (
    QFont, QColor, QKeySequence, QPalette, QShortcut, QPainter, QPen
)

# ============================================================================
# CONSTANTS
# ============================================================================

PUZZLE_TYPES = ['Logic Grid', 'Nonogram', 'Word Logic', 'Kakuro', 'Word Search']
DIFFICULTY_LEVELS = ['Easy', 'Medium', 'Hard']

LIGHT_THEME = {
    'bg': '#f5f6fa', 'surface': 'white', 'text': '#2c3e50',
    'border': '#dcdde1', 'accent': '#3498db', 'header_bg': '#34495e',
    'header_text': 'white', 'yes_bg': '#27ae60', 'no_bg': '#e74c3c',
    'empty_bg': '#ecf0f1', 'muted': '#7f8c8d', 'grid_line': '#bdc3c7',
    'highlight': '#3498db', 'note_color': '#8e44ad',
    'kakuro_block': '#34495e',
}

DARK_THEME = {
    'bg': '#1a1a2e', 'surface': '#16213e', 'text': '#e0e0e0',
    'border': '#2c3e50', 'accent': '#00b4d8', 'header_bg': '#0f3460',
    'header_text': '#e0e0e0', 'yes_bg': '#2d6a4f', 'no_bg': '#9b2226',
    'empty_bg': '#1e2a47', 'muted': '#7f8c8d', 'grid_line': '#2c3e50',
    'highlight': '#00b4d8', 'note_color': '#c77dff',
    'kakuro_block': '#0f3460',
}

# ============================================================================
# UNDO / REDO / TIMER / STATISTICS
# ============================================================================

class UndoRedoStack:
    def __init__(self, max_size=100):
        self._undo = []
        self._redo = []
        self._max = max_size

    def push(self, state):
        self._undo.append(copy.deepcopy(state))
        if len(self._undo) > self._max:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, current_state):
        if not self._undo:
            return None
        self._redo.append(copy.deepcopy(current_state))
        return self._undo.pop()

    def redo(self, current_state):
        if not self._redo:
            return None
        self._undo.append(copy.deepcopy(current_state))
        return self._redo.pop()

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def clear(self):
        self._undo.clear()
        self._redo.clear()

class SolveTimer:
    def __init__(self):
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._elapsed = QElapsedTimer()
        self._accumulated = 0
        self._running = False
        self._tick_callback = None

    def set_callback(self, cb):
        self._tick_callback = cb

    def start(self):
        if not self._running:
            self._elapsed.start()
            self._timer.start()
            self._running = True

    def pause(self):
        if self._running:
            self._accumulated += self._elapsed.elapsed()
            self._timer.stop()
            self._running = False

    def reset(self):
        self._timer.stop()
        self._running = False
        self._accumulated = 0

    def elapsed_seconds(self):
        total = self._accumulated
        if self._running:
            total += self._elapsed.elapsed()
        return total // 1000

    def _tick(self):
        if self._tick_callback:
            m, s = divmod(self.elapsed_seconds(), 60)
            self._tick_callback(f"  {m:02d}:{s:02d}")

class SolveStatistics:
    def __init__(self):
        self.records = []
        self._save_path = Path.home() / ".logic_puzzle_maker_stats.json"
        self._load()

    def _load(self):
        try:
            if self._save_path.exists():
                with open(self._save_path, "r") as f:
                    self.records = json.load(f)
        except Exception:
            self.records = []

    def _save(self):
        try:
            with open(self._save_path, "w") as f:
                json.dump(self.records[-200:], f, indent=2)
        except Exception:
            pass

    def record_solve(self, puzzle_type, title, difficulty, elapsed_secs, hints, correct):
        entry = {
            "type": puzzle_type, "title": title, "difficulty": difficulty,
            "time": elapsed_secs, "hints": hints, "correct": correct,
            "timestamp": time.time()
        }
        self.records.append(entry)
        self._save()

    def get_summary(self):
        total = len(self.records)
        if total == 0:
            return {"total_solved": 0}
        correct = sum(1 for r in self.records if r.get("correct"))
        times = [r["time"] for r in self.records if r.get("correct")]
        by_type = defaultdict(int)
        for r in self.records:
            if r.get("correct"):
                by_type[r["type"]] += 1
        return {
            "total_solved": total, "correct": correct,
            "avg_time": sum(times) // len(times) if times else 0,
            "best_time": min(times) if times else 0,
            "by_type": dict(by_type),
        }


# ============================================================================
# DATA MODELS
# ============================================================================

class PuzzleCategory:
    def __init__(self, name="", items=None):
        self.name = name
        self.items = items or []

    def to_dict(self):
        return {"name": self.name, "items": list(self.items)}

    @classmethod
    def from_dict(cls, d):
        return cls(d["name"], list(d["items"]))

class BasePuzzle:
    type_name = "base"
    def __init__(self):
        self.title = "Untitled Puzzle"
        self.difficulty = "Medium"
        self.clues = []
        self.notes = ""
    def is_valid(self):
        return True
    def get_progress(self):
        return 0.0
    def to_dict(self):
        return {
            "type": self.type_name, "title": self.title,
            "difficulty": self.difficulty, "clues": list(self.clues),
            "notes": self.notes,
        }
    @classmethod
    def from_dict(cls, d):
        raise NotImplementedError

class LogicGridPuzzle(BasePuzzle):
    type_name = "Logic Grid"
    def __init__(self):
        super().__init__()
        self.categories = []
        self.solution = {}

    def add_category(self, cat):
        self.categories.append(cat)

    def remove_category(self, idx):
        if 0 <= idx < len(self.categories):
            self.categories.pop(idx)
            self.solution.pop(idx, None)

    def grid_size(self):
        return len(self.categories[0].items) if self.categories else 0

    def is_valid(self):
        if len(self.categories) < 2:
            return False
        sz = len(self.categories[0].items)
        return all(len(c.items) == sz and sz >= 2 for c in self.categories)

    def to_dict(self):
        d = super().to_dict()
        d["categories"] = [c.to_dict() for c in self.categories]
        d["solution"] = {str(k): v for k, v in self.solution.items()}
        return d

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.title = d.get("title", "Untitled")
        p.difficulty = d.get("difficulty", "Medium")
        p.clues = list(d.get("clues", []))
        p.notes = d.get("notes", "")
        p.categories = [PuzzleCategory.from_dict(c) for c in d.get("categories", [])]
        p.solution = {int(k): v for k, v in d.get("solution", {}).items()}
        return p

class NonogramPuzzle(BasePuzzle):
    type_name = "Nonogram"
    def __init__(self):
        super().__init__()
        self.width = 10
        self.height = 10
        self.solution = []
        self.row_clues = []
        self.col_clues = []

    def is_valid(self):
        return self.width >= 2 and self.height >= 2 and bool(self.solution)

    def to_dict(self):
        d = super().to_dict()
        d.update(width=self.width, height=self.height, solution=self.solution,
                 row_clues=self.row_clues, col_clues=self.col_clues)
        return d

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.title = d.get("title", "Untitled Nonogram")
        p.difficulty = d.get("difficulty", "Medium")
        p.clues = list(d.get("clues", []))
        p.notes = d.get("notes", "")
        p.width = d.get("width", 10)
        p.height = d.get("height", 10)
        p.solution = d.get("solution", [])
        p.row_clues = d.get("row_clues", [])
        p.col_clues = d.get("col_clues", [])
        return p

class WordLogicPuzzle(BasePuzzle):
    type_name = "Word Logic"
    def __init__(self):
        super().__init__()
        self.variables = []
        self.constraints = []
        self.solution = {}

    def is_valid(self):
        return len(self.variables) >= 2

    def to_dict(self):
        d = super().to_dict()
        d.update(variables=self.variables, constraints=self.constraints,
                 solution=self.solution)
        return d

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.title = d.get("title", "Untitled Word Logic")
        p.difficulty = d.get("difficulty", "Medium")
        p.clues = list(d.get("clues", []))
        p.notes = d.get("notes", "")
        p.variables = d.get("variables", [])
        p.constraints = d.get("constraints", [])
        p.solution = d.get("solution", {})
        return p

class KakuroPuzzle(BasePuzzle):
    type_name = "Kakuro"
    def __init__(self):
        super().__init__()
        self.rows = 8
        self.cols = 8
        self.layout = []       # 0=black, 1=clue, 2=cell
        self.row_sums = {}     # (r,c_start) -> sum
        self.col_sums = {}     # (r_start,c) -> sum
        self.solution = []     # filled numbers for cells

    def is_valid(self):
        return self.rows >= 3 and self.cols >= 3 and len(self.layout) == self.rows

    def to_dict(self):
        d = super().to_dict()
        rs = {f"{k[0]},{k[1]}": v for k, v in self.row_sums.items()}
        cs = {f"{k[0]},{k[1]}": v for k, v in self.col_sums.items()}
        d.update(rows=self.rows, cols=self.cols, layout=self.layout,
                 row_sums=rs, col_sums=cs, solution=self.solution)
        return d

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.title = d.get("title", "Untitled Kakuro")
        p.difficulty = d.get("difficulty", "Medium")
        p.clues = list(d.get("clues", []))
        p.notes = d.get("notes", "")
        p.rows = d.get("rows", 8)
        p.cols = d.get("cols", 8)
        p.layout = d.get("layout", [])
        p.row_sums = {tuple(map(int, k.split(","))): v for k, v in d.get("row_sums", {}).items()}
        p.col_sums = {tuple(map(int, k.split(","))): v for k, v in d.get("col_sums", {}).items()}
        p.solution = d.get("solution", [])
        return p

class WordSearchPuzzle(BasePuzzle):
    type_name = "Word Search"
    DIRECTIONS = [(0,1),(1,0),(1,1),(1,-1),(0,-1),(-1,0),(-1,-1),(-1,1)]

    def __init__(self):
        super().__init__()
        self.width = 12
        self.height = 12
        self.words = []
        self.grid = []
        self.placements = []  # [{word, r, c, dr, dc}]

    def is_valid(self):
        return self.width >= 5 and self.height >= 5 and bool(self.words)

    def to_dict(self):
        d = super().to_dict()
        d.update(width=self.width, height=self.height, words=self.words,
                 grid=self.grid, placements=self.placements)
        return d

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.title = d.get("title", "Untitled Word Search")
        p.difficulty = d.get("difficulty", "Medium")
        p.clues = list(d.get("clues", []))
        p.notes = d.get("notes", "")
        p.width = d.get("width", 12)
        p.height = d.get("height", 12)
        p.words = d.get("words", [])
        p.grid = d.get("grid", [])
        p.placements = d.get("placements", [])
        return p

def puzzle_from_dict(d):
    t = d.get("type", "Logic Grid")
    for cls in (LogicGridPuzzle, NonogramPuzzle, WordLogicPuzzle,
                KakuroPuzzle, WordSearchPuzzle):
        if cls.type_name == t:
            return cls.from_dict(d)
    return LogicGridPuzzle.from_dict(d)

# ============================================================================
# NONOGRAM ENGINE
# ============================================================================

class NonogramEngine:
    @staticmethod
    def compute_clues(grid):
        rows, cols = len(grid), len(grid[0]) if grid else 0
        row_clues, col_clues = [], []
        for r in range(rows):
            clue, count = [], 0
            for c in range(cols):
                if grid[r][c] == 1:
                    count += 1
                elif count:
                    clue.append(count); count = 0
            if count:
                clue.append(count)
            row_clues.append(clue if clue else [0])
        for c in range(cols):
            clue, count = [], 0
            for r in range(rows):
                if grid[r][c] == 1:
                    count += 1
                elif count:
                    clue.append(count); count = 0
            if count:
                clue.append(count)
            col_clues.append(clue if clue else [0])
        return row_clues, col_clues

    @staticmethod
    def generate(width=10, height=10, difficulty="Medium"):
        puzzle = NonogramPuzzle()
        puzzle.width, puzzle.height = width, height
        ratio = {"Easy": 0.3, "Medium": 0.45, "Hard": 0.6}.get(difficulty, 0.45)
        grid = [[0] * width for _ in range(height)]
        for _ in range(random.randint(2, 6)):
            cr, cc = random.randint(0, height - 1), random.randint(0, width - 1)
            for _ in range(random.randint(2, max(2, min(width, height) // 2))):
                r = cr + random.randint(-2, 2)
                c = cc + random.randint(-2, 2)
                if 0 <= r < height and 0 <= c < width:
                    grid[r][c] = 1
        puzzle.solution = grid
        puzzle.row_clues, puzzle.col_clues = NonogramEngine.compute_clues(grid)
        puzzle.difficulty = difficulty
        puzzle.title = f"Nonogram {width}x{height} ({difficulty})"
        return puzzle


# ============================================================================
# LOGIC GRID GENERATOR / SOLVER / AUTO-CLUES / DIFFICULTY
# ============================================================================

class LogicGridSolver:
    @staticmethod
    def solve(puzzle):
        cats = puzzle.categories
        if len(cats) < 2:
            return None
        sz = puzzle.grid_size()
        if sz < 2:
            return None
        poss = {}
        for ci in range(len(cats)):
            for ri in range(sz):
                poss[(ci, ri)] = set(range(sz))
        if puzzle.solution:
            for ci, si in puzzle.solution.items():
                if 0 <= ci < len(cats) and 0 <= si < sz:
                    for ri in range(sz):
                        if ri != si:
                            poss[(ci, ri)].discard(si)
        LogicGridSolver._apply_clue_constraints(puzzle, poss, cats, sz)
        changed = True
        while changed:
            changed = False
            for ci in range(len(cats)):
                for ri in range(sz):
                    if len(poss[(ci, ri)]) == 1:
                        val = next(iter(poss[(ci, ri)]))
                        for ri2 in range(sz):
                            if ri2 != ri and val in poss[(ci, ri2)]:
                                poss[(ci, ri2)].discard(val)
                                changed = True
        return LogicGridSolver._backtrack(poss, cats, sz, 0)

    @staticmethod
    def _apply_clue_constraints(puzzle, poss, cats, sz):
        for clue in puzzle.clues:
            cl = clue.lower()
            for ci in range(1, len(cats)):
                for ri, ia in enumerate(cats[0].items):
                    for si, ib in enumerate(cats[ci].items):
                        for pat in [f"{ia.lower()} does not have {ib.lower()}",
                                    f"{ia.lower()} is not {ib.lower()}",
                                    f"{ia.lower()} doesn't have {ib.lower()}"]:
                            if pat in cl:
                                poss[(ci, ri)].discard(si)
                        for pat in [f"{ia.lower()} has {ib.lower()}",
                                    f"{ia.lower()} goes with {ib.lower()}",
                                    f"{ia.lower()} is {ib.lower()}"]:
                            if pat in cl:
                                for v in set(range(sz)) - {si}:
                                    poss[(ci, ri)].discard(v)

    @staticmethod
    def _backtrack(poss, cats, sz, ci):
        if ci >= len(cats):
            return {}
        for perm in permutations(range(sz)):
            if all(perm[ri] in poss[(ci, ri)] for ri in range(sz)):
                old = {k: set(v) for k, v in poss.items()}
                for ri in range(sz):
                    for ci2 in range(len(cats)):
                        if ci2 != ci:
                            for ri2 in range(sz):
                                if ri2 != ri:
                                    poss[(ci2, ri2)].discard(perm[ri])
                result = LogicGridSolver._backtrack(poss, cats, sz, ci + 1) if ci + 1 < len(cats) else {}
                if result is not None:
                    result[ci] = perm
                    return result
                poss.update(old)
        return None

class AutoClueGenerator:
    @staticmethod
    def generate(puzzle, difficulty="Medium"):
        cats = puzzle.categories
        sz = puzzle.grid_size()
        sol = puzzle.solution
        if len(cats) < 2 or not sol:
            return []
        pool = []
        # Direct matches
        for ci in range(1, len(cats)):
            if 0 in sol and ci in sol:
                a = cats[0].items[sol[0]]
                b = cats[ci].items[sol[ci]]
                pool.append(f"{a} has {b}.")
        # Negatives
        for ci in range(1, len(cats)):
            if 0 in sol and ci in sol:
                a = cats[0].items[sol[0]]
                others = [cats[ci].items[i] for i in range(sz) if i != sol[ci]]
                if others:
                    pool.append(f"{a} does not have {random.choice(others)}.")
        # Cross-category
        if len(cats) >= 3 and 1 in sol and 2 in sol:
            pool.append(f"The person with {cats[1].items[sol[1]]} also has {cats[2].items[sol[2]]}.")
        # Ordering
        if sz >= 3 and len(cats) >= 2:
            a = random.randint(0, sz - 1)
            others = [x for x in range(sz) if x != a]
            b = random.choice(others)
            lo, hi = min(a, b), max(a, b)
            pool.append(f"{cats[0].items[a]} is somewhere between {cats[1].items[lo]} and {cats[1].items[hi]} in position.")
        # Neither/nor
        if sz >= 3 and len(cats) >= 2 and 1 in sol:
            others = [cats[1].items[i] for i in range(sz) if i != sol[1]]
            if len(others) >= 2:
                pair = random.sample(others, 2)
                ci = random.randint(2, len(cats) - 1) if len(cats) > 2 else 1
                if ci in sol:
                    pool.append(f"Neither {pair[0]} nor {pair[1]} has {cats[ci].items[sol[ci]]}.")
        num = {"Easy": sz + 3, "Medium": sz + 1, "Hard": max(sz - 1, 2)}.get(difficulty, sz + 1)
        random.shuffle(pool)
        return pool[:num]

class DifficultyScorer:
    @staticmethod
    def score(puzzle):
        t = puzzle.type_name
        if t == "Logic Grid" and isinstance(puzzle, LogicGridPuzzle):
            sz = puzzle.grid_size()
            nc = len(puzzle.categories)
            ncl = len(puzzle.clues)
            size_s = min(sz * 8, 40)
            cat_s = min(nc * 5, 25)
            possible = sz * (nc - 1) * 2
            ratio = max(0, 1 - (ncl / max(possible, 1)))
            clue_s = int(ratio * 35)
            return min(max(10 + size_s + cat_s + clue_s, 10), 100)
        elif t == "Nonogram":
            area = puzzle.width * puzzle.height
            filled = sum(sum(r) for r in puzzle.solution) if puzzle.solution else 0
            s = min(area // 5, 40)
            d = filled / max(area, 1)
            ds = int(abs(0.5 - d) * 60)
            return min(max(15 + s + ds, 10), 100)
        elif t == "Kakuro":
            area = puzzle.rows * puzzle.cols
            nc = len(puzzle.row_sums) + len(puzzle.col_sums)
            return min(max(20 + area + nc * 2, 10), 100)
        elif t == "Word Search":
            n = len(puzzle.words)
            area = puzzle.width * puzzle.height
            return min(max(n * 5 + area // 10, 10), 100)
        return 50

class LogicGridGenerator:
    TEMPLATES = {
        3: [("Owners", ["Alice", "Bob", "Carol"]),
            ("Pets", ["Dog", "Cat", "Bird"]),
            ("Colors", ["Red", "Blue", "Green"])],
        4: [("Owners", ["Alice", "Bob", "Carol", "David"]),
            ("Pets", ["Dog", "Cat", "Bird", "Fish"]),
            ("Colors", ["Red", "Blue", "Green", "Yellow"]),
            ("Cities", ["Paris", "Tokyo", "Cairo", "Sydney"])],
        5: [("Owners", ["Alice", "Bob", "Carol", "David", "Eve"]),
            ("Pets", ["Dog", "Cat", "Bird", "Fish", "Rabbit"]),
            ("Colors", ["Red", "Blue", "Green", "Yellow", "Purple"]),
            ("Cities", ["Paris", "Tokyo", "Cairo", "Sydney", "Lima"]),
            ("Drinks", ["Tea", "Coffee", "Juice", "Water", "Milk"])],
    }

    @staticmethod
    def generate(size=4, difficulty="Medium"):
        size = max(2, min(5, size))
        templates = LogicGridGenerator.TEMPLATES.get(size, LogicGridGenerator.TEMPLATES[4])
        puzzle = LogicGridPuzzle()
        for name, items in templates:
            ic = list(items[:size])
            random.shuffle(ic)
            puzzle.add_category(PuzzleCategory(name, ic))
        sol_idx = list(range(size))
        random.shuffle(sol_idx)
        for ci, si in enumerate(sol_idx):
            puzzle.solution[ci] = si
        puzzle.clues = AutoClueGenerator.generate(puzzle, difficulty)
        puzzle.difficulty = difficulty
        puzzle.title = f"Logic Grid {size}x{size} ({difficulty})"
        return puzzle


# ============================================================================
# WORD LOGIC GENERATOR
# ============================================================================

class WordLogicGenerator:
    VARIABLE_SETS = [[
        {"name": "Nationality", "domain": ["Norwegian", "Englishman", "Swede", "Dane", "German"]},
        {"name": "Color", "domain": ["Red", "Green", "White", "Yellow", "Blue"]},
        {"name": "Drink", "domain": ["Tea", "Coffee", "Milk", "Beer", "Water"]},
        {"name": "Pet", "domain": ["Cats", "Dogs", "Birds", "Horses", "Fish"]},
        {"name": "Smoke", "domain": ["Pall Mall", "Dunhill", "Blends", "Blue Master", "Prince"]},
    ]]

    @staticmethod
    def generate(size=5, difficulty="Medium"):
        puzzle = WordLogicPuzzle()
        template = WordLogicGenerator.VARIABLE_SETS[0]
        indices = list(range(size))
        random.shuffle(indices)
        puzzle.variables = []
        puzzle.solution = {}
        for vi, var in enumerate(template):
            domain = list(var["domain"][:size])
            random.shuffle(domain)
            puzzle.variables.append({"name": var["name"], "domain": domain})
            puzzle.solution[var["name"]] = domain[indices[vi]]
        ctypes = ["not_equal", "equal", "left_of"]
        nc = {"Easy": 8, "Medium": 6, "Hard": 4}.get(difficulty, 6)
        puzzle.clues = []
        puzzle.constraints = []
        for _ in range(nc):
            ct = random.choice(ctypes)
            v1 = random.choice(puzzle.variables)
            v2 = random.choice([v for v in puzzle.variables if v["name"] != v1["name"]])
            i1 = random.choice(v1["domain"])
            i2 = random.choice(v2["domain"])
            n1, n2 = v1["name"], v2["name"]
            if ct == "equal":
                if i1 == puzzle.solution.get(n1) and i2 == puzzle.solution.get(n2):
                    text = f"The {n1} {i1} goes with {n2} {i2}."
                else:
                    text = f"The {n1} {i1} does NOT go with {n2} {i2}."
                    ct = "not_equal"
                puzzle.clues.append(text)
                puzzle.constraints.append({"text": text, "type": ct,
                    "vars": [n1, n2], "params": {"values": [i1, i2]}})
            elif ct == "not_equal":
                text = f"{n1} {i1} is not the same as {n2} {i2}."
                puzzle.clues.append(text)
                puzzle.constraints.append({"text": text, "type": "not_equal",
                    "vars": [n1, n2], "params": {"values": [i1, i2]}})
            elif ct == "left_of":
                text = f"The {n1} {i1} is to the left of {n2} {i2}."
                puzzle.clues.append(text)
                puzzle.constraints.append({"text": text, "type": "left_of",
                    "vars": [n1, n2], "params": {"values": [i1, i2]}})
        puzzle.difficulty = difficulty
        puzzle.title = f"Word Logic ({difficulty})"
        return puzzle


# ============================================================================
# KAKURO ENGINE
# ============================================================================

class KakuroEngine:
    @staticmethod
    def generate(rows=8, cols=8, difficulty="Medium"):
        puzzle = KakuroPuzzle()
        puzzle.rows, puzzle.cols = rows, cols

        # Create layout: 0=black, 1=clue cell, 2=playable cell
        layout = [[0] * cols for _ in range(rows)]
        # Ensure border is black/clue, interior is playable
        # Place clue cells at starts of runs
        for r in range(rows):
            for c in range(cols):
                if r == 0 or c == 0 or r == rows - 1 or c == cols - 1:
                    layout[r][c] = 0  # border black
                else:
                    layout[r][c] = 2  # default playable

        # Make some interior cells black to create runs
        num_black = {"Easy": rows // 3, "Medium": rows // 2, "Hard": rows}.get(difficulty, rows // 2)
        for _ in range(num_black):
            r = random.randint(1, rows - 2)
            c = random.randint(1, cols - 2)
            layout[r][c] = 0

        # Mark clue cells: a cell adjacent (right or below) to a black cell
        # that starts a horizontal or vertical run becomes a clue cell
        for r in range(rows):
            for c in range(cols):
                if layout[r][c] == 0:
                    # Cell to the right
                    if c + 1 < cols and layout[r][c + 1] == 2:
                        layout[r][c + 1] = 1
                    # Cell below
                    if r + 1 < rows and layout[r + 1][c] == 2:
                        layout[r + 1][c] = 1
        # Fix: cells that are clue cells are not playable
        # After marking clues, re-check that runs still exist
        # For simplicity, convert clue cells back if they break things

        # Identify runs and fill with valid numbers
        solution = [[0] * cols for _ in range(rows)]
        row_sums = {}
        col_sums = {}

        # Process horizontal runs
        for r in range(rows):
            c = 1
            while c < cols:
                if layout[r][c] == 1:
                    # This is a clue cell - the run starts at c+1
                    run_start = c + 1
                    if run_start >= cols or layout[r][run_start] != 2:
                        c += 1
                        continue
                    run_len = 0
                    while run_start + run_len < cols and layout[r][run_start + run_len] == 2:
                        run_len += 1
                    if run_len >= 1:
                        # Fill with unique 1-9
                        available = list(range(1, 10))
                        random.shuffle(available)
                        nums = available[:run_len]
                        s = sum(nums)
                        row_sums[(r, run_start)] = s
                        for k in range(run_len):
                            solution[r][run_start + k] = nums[k]
                    c = run_start + run_len if run_len >= 1 else c + 1
                else:
                    c += 1

        # Process vertical runs
        for c in range(cols):
            r = 1
            while r < rows:
                if layout[r][c] == 1:
                    run_start = r + 1
                    if run_start >= rows or layout[run_start][c] != 2:
                        r += 1
                        continue
                    run_len = 0
                    while run_start + run_len < rows and layout[run_start + run_len][c] == 2:
                        run_len += 1
                    if run_len >= 1:
                        available = list(range(1, 10))
                        random.shuffle(available)
                        nums = available[:run_len]
                        s = sum(nums)
                        col_sums[(run_start, c)] = s
                        for k in range(run_len):
                            solution[run_start + k][c] = nums[k]
                    r = run_start + run_len if run_len >= 1 else r + 1
                else:
                    r += 1

        puzzle.layout = layout
        puzzle.row_sums = row_sums
        puzzle.col_sums = col_sums
        puzzle.solution = solution
        puzzle.difficulty = difficulty
        puzzle.title = f"Kakuro {rows}x{cols} ({difficulty})"
        return puzzle


# ============================================================================
# WORD SEARCH ENGINE
# ============================================================================

class WordSearchEngine:
    WORD_SETS = {
        "Animals": ["CAT", "DOG", "BIRD", "FISH", "LION", "TIGER", "BEAR", "WOLF",
                     "DEER", "EAGLE", "SNAKE", "HORSE", "SHARK", "WHALE", "PANDA"],
        "Fruits": ["APPLE", "BANANA", "GRAPE", "MANGO", "PEACH", "PLUM", "LEMON",
                    "CHERRY", "MELON", "BERRY", "KIWI", "PEAR", "FIG", "LIME", "DATE"],
        "Science": ["ATOM", "CELL", "GENE", "WAVE", "MASS", "HEAT", "LENS", "ION",
                     "PROTON", "NEUTRON", "PHOTON", "PLASMA", "QUARK", "ORBIT", "FORCE"],
        "Nature": ["RIVER", "OCEAN", "STORM", "CLOUD", "STONE", "FLAME", "FROST",
                    "EARTH", "LAKE", "HILL", "CAVE", "RAIN", "SNOW", "WIND", "TREE"],
    }

    @staticmethod
    def generate(width=12, height=12, difficulty="Medium", category=None):
        puzzle = WordSearchPuzzle()
        puzzle.width, puzzle.height = width, height
        if not category:
            category = random.choice(list(WordSearchEngine.WORD_SETS.keys()))
        word_pool = list(WordSearchEngine.WORD_SETS[category])
        random.shuffle(word_pool)

        # Filter words that fit
        max_len = max(width, height)
        word_pool = [w for w in word_pool if len(w) <= max_len]

        # Number of words based on difficulty
        num_words = {"Easy": 5, "Medium": 8, "Hard": 12}.get(difficulty, 8)
        num_dirs = {"Easy": 3, "Medium": 5, "Hard": 8}.get(difficulty, 5)
        dirs = WordSearchPuzzle.DIRECTIONS[:num_dirs]

        grid = [[""] * width for _ in range(height)]
        placed_words = []

        for word in word_pool:
            if len(placed_words) >= num_words:
                break
            random.shuffle(dirs)
            for dr, dc in dirs:
                for _ in range(50):
                    r = random.randint(0, height - 1)
                    c = random.randint(0, width - 1)
                    er, ec = r + dr * (len(word) - 1), c + dc * (len(word) - 1)
                    if not (0 <= er < height and 0 <= ec < width):
                        continue
                    ok = True
                    for i, ch in enumerate(word):
                        nr, nc = r + dr * i, c + dc * i
                        if grid[nr][nc] not in ("", ch):
                            ok = False
                            break
                    if ok:
                        for i, ch in enumerate(word):
                            grid[r + dr * i][c + dc * i] = ch
                        placed_words.append({"word": word, "r": r, "c": c, "dr": dr, "dc": dc})
                        break
                if len(placed_words) > 0 and placed_words[-1]["word"] == word:
                    break

        # Fill empty cells with random letters
        for r in range(height):
            for c in range(width):
                if grid[r][c] == "":
                    grid[r][c] = chr(random.randint(65, 90))

        puzzle.grid = grid
        puzzle.words = [pw["word"] for pw in placed_words]
        puzzle.placements = placed_words
        puzzle.difficulty = difficulty
        puzzle.title = f"Word Search - {category} ({difficulty})"
        puzzle.clues = [f"Find: {w}" for w in puzzle.words]
        return puzzle

# ============================================================================
# HELPER
# ============================================================================

def _get_text(parent, title, label, default=""):
    text, ok = QLineEdit.getText(parent, title, label, text=default)
    return text, ok


# ============================================================================
# DIALOGS
# ============================================================================

class NewPuzzleDialog(QDialog):
    def __init__(self, parent=None, theme=None):
        super().__init__(parent)
        self.setWindowTitle("New Puzzle")
        self.setMinimumWidth(520)
        self.chosen_type = "Logic Grid"
        self.chosen_difficulty = "Medium"
        self.auto_generate = True
        self.puzzle_params = {}
        t = theme or LIGHT_THEME
        self._setup(t)

    def _setup(self, t):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Create a New Puzzle</h3>"))

        type_group = QGroupBox("Puzzle Type")
        type_layout = QGridLayout(type_group)
        self.type_buttons = []
        descs = [
            ("Logic Grid", "Deduce which items go together\nusing clues (e.g., who owns which pet?)"),
            ("Nonogram", "Fill cells to reveal a hidden picture\nusing row/column number clues"),
            ("Word Logic", "Einstein-style riddles with\nconstraint clues across variables"),
            ("Kakuro", "Fill numbers so row/column\nruns sum to the given clues"),
            ("Word Search", "Find hidden words in a\nletter grid (any direction)"),
        ]
        icons = ["\U0001f4ca", "\U0001f7e9", "\U0001f9e0", "\U0001f522", "\U0001f50d"]
        for i, (name, desc) in enumerate(descs):
            rb = QRadioButton(f"  {icons[i]}  {name}")
            rb.setFont(QFont("Segoe UI", 11))
            rb.setChecked(i == 0)
            dl = QLabel(desc)
            dl.setStyleSheet(f"color: {t['muted']}; font-size: 11px; padding-left: 32px;")
            dl.setWordWrap(True)
            self.type_buttons.append(rb)
            rb.toggled.connect(lambda checked, idx=i: self._on_type(idx, checked))
            type_layout.addWidget(rb, i, 0)
            type_layout.addWidget(dl, i, 1)
        self.type_buttons[0].setChecked(True)
        layout.addWidget(type_group)

        diff_group = QGroupBox("Difficulty")
        diff_layout = QHBoxLayout(diff_group)
        self.diff_buttons = []
        for i, d in enumerate(DIFFICULTY_LEVELS):
            rb = QRadioButton(d)
            rb.setChecked(i == 1)
            self.diff_buttons.append(rb)
            diff_layout.addWidget(rb)
        layout.addWidget(diff_group)

        self.auto_gen_cb = QCheckBox("  Auto-generate puzzle (random)")
        self.auto_gen_cb.setChecked(True)
        self.auto_gen_cb.setStyleSheet("font-size: 13px; padding: 6px;")
        layout.addWidget(self.auto_gen_cb)

        self.params_group = QGroupBox("Parameters")
        self.params_layout = QFormLayout(self.params_group)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(2, 5)
        self.size_spin.setValue(4)
        self.params_layout.addRow("Grid Size:", self.size_spin)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(5, 25)
        self.width_spin.setValue(10)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(5, 25)
        self.height_spin.setValue(10)
        self.wh_widget = QWidget()
        whl = QHBoxLayout(self.wh_widget)
        whl.setContentsMargins(0, 0, 0, 0)
        whl.addWidget(QLabel("W:"))
        whl.addWidget(self.width_spin)
        whl.addWidget(QLabel("H:"))
        whl.addWidget(self.height_spin)
        self.params_layout.addRow("Grid Size:", self.wh_widget)
        self.wh_widget.hide()
        layout.addWidget(self.params_group)

        self.word_cat_combo = QComboBox()
        self.word_cat_combo.addItems(list(WordSearchEngine.WORD_SETS.keys()))
        self.params_layout.addRow("Word Category:", self.word_cat_combo)
        self.word_cat_combo.hide()

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Create")
        ok_btn.clicked.connect(self._accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_type(self, idx, checked):
        if not checked:
            return
        names = ["Logic Grid", "Nonogram", "Word Logic", "Kakuro", "Word Search"]
        self.chosen_type = names[idx]
        self.size_spin.show() if idx == 0 else self.size_spin.hide()
        if idx in (1, 3):  # Nonogram, Kakuro need W/H
            self.wh_widget.show()
        else:
            self.wh_widget.hide()
        self.word_cat_combo.show() if idx == 4 else self.word_cat_combo.hide()

    def _accept(self):
        for i, rb in enumerate(self.diff_buttons):
            if rb.isChecked():
                self.chosen_difficulty = DIFFICULTY_LEVELS[i]
                break
        self.auto_generate = self.auto_gen_cb.isChecked()
        self.puzzle_params = {
            "size": self.size_spin.value(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "word_category": self.word_cat_combo.currentText(),
        }
        self.accept()

class CategoryDialog(QDialog):
    def __init__(self, parent=None, category=None, required_size=0, theme=None):
        super().__init__(parent)
        self.required_size = required_size
        self.category = None
        self.setWindowTitle("Edit Category" if category else "Add Category")
        self.setMinimumWidth(420)
        self._setup()
        if category:
            self._load(category)

    def _setup(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Names, Colors, Pets, Cities...")
        form.addRow("Category Name:", self.name_edit)
        if self.required_size:
            hint = QLabel(f"This puzzle requires {self.required_size} items per category.")
            hint.setStyleSheet("color: #e67e22; font-style: italic;")
            form.addRow(hint)
        layout.addLayout(form)
        items_group = QGroupBox("Items")
        items_layout = QVBoxLayout(items_group)
        self.items_list = QListWidget()
        self.items_list.setSelectionMode(QAbstractItemView.SingleSelection)
        items_layout.addWidget(self.items_list)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Item")
        remove_btn = QPushButton("- Remove")
        remove_btn.setEnabled(False)
        add_btn.clicked.connect(self._add_item)
        remove_btn.clicked.connect(self._remove_item)
        self.items_list.currentRowChanged.connect(lambda r: remove_btn.setEnabled(r >= 0))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        items_layout.addLayout(btn_row)
        layout.addWidget(items_group)
        quick_row = QHBoxLayout()
        self.quick_edit = QLineEdit()
        self.quick_edit.setPlaceholderText("Quick add: item1, item2, item3 ...")
        quick_btn = QPushButton("Add All")
        quick_btn.clicked.connect(self._quick_add)
        quick_row.addWidget(self.quick_edit)
        quick_row.addWidget(quick_btn)
        layout.addLayout(quick_row)
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self._accept)
        cancel_btn.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def _load(self, cat):
        self.name_edit.setText(cat.name)
        for item in cat.items:
            self.items_list.addItem(item)

    def _add_item(self):
        text, ok = _get_text(self, "Add Item", "Item name:")
        if ok and text.strip():
            self.items_list.addItem(text.strip())

    def _remove_item(self):
        row = self.items_list.currentRow()
        if row >= 0:
            self.items_list.takeItem(row)

    def _quick_add(self):
        for s in [x.strip() for x in self.quick_edit.text().split(",") if x.strip()]:
            self.items_list.addItem(s)
        self.quick_edit.clear()

    def _accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Warning", "Enter a category name.")
            return
        items = [self.items_list.item(i).text().strip()
                 for i in range(self.items_list.count())
                 if self.items_list.item(i).text().strip()]
        if not items:
            QMessageBox.warning(self, "Warning", "Add at least one item.")
            return
        if self.required_size and len(items) != self.required_size:
            QMessageBox.warning(self, "Size Mismatch",
                f"Expected {self.required_size} items, got {len(items)}.")
            return
        self.category = PuzzleCategory(name, items)
        self.accept()

class SolutionDialog(QDialog):
    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.setWindowTitle("Set Solution")
        self.setMinimumWidth(520)
        self.solution = dict(puzzle.solution)
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select the correct item from each category."))
        layout.addWidget(QLabel("The first category defines rows; pick the matching item from each other."))
        layout.addSpacing(8)
        if not self.puzzle.categories:
            layout.addWidget(QLabel("No categories defined yet."))
            return
        self.combos = []
        for ci, cat in enumerate(self.puzzle.categories):
            row_l = QHBoxLayout()
            lbl = QLabel(f"<b>{cat.name}:</b>")
            lbl.setFixedWidth(130)
            combo = QComboBox()
            combo.addItem("-- select --")
            for idx, item in enumerate(cat.items):
                combo.addItem(f"{idx + 1}. {item}")
            if ci in self.solution:
                combo.setCurrentIndex(self.solution[ci] + 1)
            row_l.addWidget(lbl)
            row_l.addWidget(combo, 1)
            layout.addLayout(row_l)
            self.combos.append((ci, combo))
        layout.addSpacing(8)
        btn_box = QHBoxLayout()
        for text, slot in [("Save Solution", self._save), ("Clear", self._clear), ("Cancel", self.reject)]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            btn_box.addWidget(b)
        btn_box.addStretch()
        layout.addLayout(btn_box)

    def _save(self):
        self.solution.clear()
        for ci, combo in self.combos:
            idx = combo.currentIndex() - 1
            if idx < 0:
                QMessageBox.warning(self, "Incomplete",
                    f"Select an item for {self.puzzle.categories[ci].name}.")
                return
            self.solution[ci] = idx
        self.accept()

    def _clear(self):
        for _, c in self.combos:
            c.setCurrentIndex(0)
        self.solution.clear()

class WordLogicEditorDialog(QDialog):
    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.setWindowTitle("Edit Word Logic Variables & Constraints")
        self.setMinimumSize(600, 500)
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        # Variables tab
        var_tab = QWidget()
        var_layout = QVBoxLayout(var_tab)
        self.var_list = QListWidget()
        for v in self.puzzle.variables:
            self.var_list.addItem(f"{v['name']}: {', '.join(v['domain'])}")
        var_layout.addWidget(QLabel("Variables (name: value1, value2, ...)"))
        var_layout.addWidget(self.var_list)
        var_btn = QHBoxLayout()
        add_v = QPushButton("Add Variable")
        edit_v = QPushButton("Edit")
        del_v = QPushButton("Remove")
        del_v.setObjectName("danger")
        add_v.clicked.connect(self._add_var)
        edit_v.clicked.connect(self._edit_var)
        del_v.clicked.connect(self._del_var)
        var_btn.addWidget(add_v)
        var_btn.addWidget(edit_v)
        var_btn.addWidget(del_v)
        var_layout.addLayout(var_btn)
        tabs.addTab(var_tab, "Variables")
        # Constraints tab
        con_tab = QWidget()
        con_layout = QVBoxLayout(con_tab)
        self.con_list = QListWidget()
        for c in self.puzzle.constraints:
            self.con_list.addItem(c.get("text", ""))
        con_layout.addWidget(QLabel("Constraints / Clues"))
        con_layout.addWidget(self.con_list)
        con_btn = QHBoxLayout()
        add_c = QPushButton("Add Constraint")
        edit_c = QPushButton("Edit")
        del_c = QPushButton("Remove")
        del_c.setObjectName("danger")
        add_c.clicked.connect(self._add_con)
        edit_c.clicked.connect(self._edit_con)
        del_c.clicked.connect(self._del_con)
        con_btn.addWidget(add_c)
        con_btn.addWidget(edit_c)
        con_btn.addWidget(del_c)
        con_layout.addLayout(con_btn)
        tabs.addTab(con_tab, "Constraints")
        layout.addWidget(tabs)
        # Solution tab
        sol_tab = QWidget()
        sol_layout = QVBoxLayout(sol_tab)
        sol_layout.addWidget(QLabel("Set the correct value for each variable:"))
        self.sol_combos = []
        for v in self.puzzle.variables:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{v['name']}:</b>"))
            combo = QComboBox()
            combo.addItem("-- select --")
            for val in v["domain"]:
                combo.addItem(val)
            if v["name"] in self.puzzle.solution:
                idx = v["domain"].index(self.puzzle.solution[v["name"]]) if self.puzzle.solution[v["name"]] in v["domain"] else -1
                if idx >= 0:
                    combo.setCurrentIndex(idx + 1)
            row.addWidget(combo, 1)
            sol_layout.addLayout(row)
            self.sol_combos.append((v["name"], combo))
        tabs.addTab(sol_tab, "Solution")
        btn_row = QHBoxLayout()
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(self._accept)
        cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _add_var(self):
        name, ok = _get_text(self, "Variable Name", "Name (e.g., Color):")
        if not ok or not name.strip():
            return
        vals, ok = _get_text(self, "Values", "Comma-separated values:", "Red, Blue, Green")
        if ok and vals.strip():
            domain = [v.strip() for v in vals.split(",") if v.strip()]
            self.puzzle.variables.append({"name": name.strip(), "domain": domain})
            self.var_list.addItem(f"{name.strip()}: {', '.join(domain)}")

    def _edit_var(self):
        row = self.var_list.currentRow()
        if row < 0:
            return
        v = self.puzzle.variables[row]
        name, ok = _get_text(self, "Variable Name", "Name:", v["name"])
        if ok and name.strip():
            vals, ok2 = _get_text(self, "Values", "Comma-separated:", ", ".join(v["domain"]))
            if ok2 and vals.strip():
                v["name"] = name.strip()
                v["domain"] = [x.strip() for x in vals.split(",") if x.strip()]
                self.var_list.item(row).setText(f"{v['name']}: {', '.join(v['domain'])}")

    def _del_var(self):
        row = self.var_list.currentRow()
        if row >= 0:
            self.puzzle.variables.pop(row)
            self.var_list.takeItem(row)

    def _add_con(self):
        text, ok = _get_text(self, "Constraint", "Clue text:")
        if ok and text.strip():
            self.puzzle.constraints.append({"text": text.strip(), "type": "custom", "vars": [], "params": {}})
            self.puzzle.clues.append(text.strip())
            self.con_list.addItem(text.strip())

    def _edit_con(self):
        row = self.con_list.currentRow()
        if row < 0:
            return
        text, ok = _get_text(self, "Edit Constraint", "Clue text:",
                             self.puzzle.constraints[row].get("text", ""))
        if ok and text.strip():
            self.puzzle.constraints[row]["text"] = text.strip()
            self.puzzle.clues[row] = text.strip()
            self.con_list.item(row).setText(text.strip())

    def _del_con(self):
        row = self.con_list.currentRow()
        if row >= 0:
            self.puzzle.constraints.pop(row)
            if row < len(self.puzzle.clues):
                self.puzzle.clues.pop(row)
            self.con_list.takeItem(row)

    def _accept(self):
        self.puzzle.solution.clear()
        for name, combo in self.sol_combos:
            idx = combo.currentIndex() - 1
            if idx >= 0:
                var = next((v for v in self.puzzle.variables if v["name"] == name), None)
                if var and idx < len(var["domain"]):
                    self.puzzle.solution[name] = var["domain"][idx]
        self.accept()

class ImportTextDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Puzzle from Text")
        self.setMinimumSize(550, 450)
        self.imported_puzzle = None
        self._setup()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Import from Text</h3>"))
        layout.addWidget(QLabel("Paste a puzzle description. Supported formats:"))
        info = QLabel(
            "<ul><li><b>Logic Grid:</b> Title + categories with items + clues (one per line)</li>"
            "<li><b>Word Search:</b> Comma-separated word list</li></ul>")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Example:\n"
            "Title: The Pet Show\n"
            "Category: Owners - Alice, Bob, Carol\n"
            "Category: Pets - Dog, Cat, Bird\n"
            "Category: Colors - Red, Blue, Green\n"
            "1. Alice has a Dog.\n"
            "2. Bob does not have a Cat.\n"
            "3. The person with Red has a Bird."
        )
        layout.addWidget(self.text_edit)
        btn_row = QHBoxLayout()
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(import_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _import(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty", "Paste some text first.")
            return
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        puzzle = None

        # Try Logic Grid format
        title = "Imported Puzzle"
        categories = []
        clues = []
        for line in lines:
            if line.lower().startswith("title:"):
                title = line.split(":", 1)[1].strip()
            elif line.lower().startswith("category:"):
                rest = line.split(":", 1)[1].strip()
                if " - " in rest:
                    name, items = rest.split(" - ", 1)
                    categories.append(PuzzleCategory(name.strip(),
                        [x.strip() for x in items.split(",") if x.strip()]))
            elif re.match(r"^\d+\.\s", line):
                clues.append(re.sub(r"^\d+\.\s*", "", line))

        if len(categories) >= 2:
            puzzle = LogicGridPuzzle()
            puzzle.title = title
            puzzle.categories = categories
            puzzle.clues = clues
        else:
            # Try word search format (comma-separated words)
            words = [w.strip().upper() for w in re.split("[,\n]+", text) if w.strip() and len(w.strip()) >= 2]
            words = list(set(words))[:15]
            if len(words) >= 3:
                cat = "Custom"
                for key, wset in WordSearchEngine.WORD_SETS.items():
                    if any(w in wset for w in words):
                        cat = key
                        break
                puzzle = WordSearchEngine.generate(12, 12, "Medium", cat)
                puzzle.title = f"Word Search - Imported"
                # Add user words
                for w in words:
                    if w not in puzzle.words and len(puzzle.words) < 12:
                        puzzle.words.append(w)
                puzzle.clues = [f"Find: {w}" for w in puzzle.words]

        if puzzle:
            self.imported_puzzle = puzzle
            self.accept()
        else:
            QMessageBox.warning(self, "Failed",
                "Could not parse puzzle. Use 'Category: Name - item1, item2' format for Logic Grid.")

class StatisticsDialog(QDialog):
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Solve Statistics")
        self.setMinimumSize(450, 350)
        self._setup(stats)

    def _setup(self, stats):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Your Puzzle Statistics</h3>"))
        summary = stats.get_summary()
        form = QFormLayout()
        form.addRow("Total Solved:", QLabel(str(summary.get("total_solved", 0))))
        form.addRow("Correct:", QLabel(str(summary.get("correct", 0))))
        avg = summary.get("avg_time", 0)
        form.addRow("Average Time:", QLabel(f"{avg // 60:02d}:{avg % 60:02d}"))
        best = summary.get("best_time", 0)
        form.addRow("Best Time:", QLabel(f"{best // 60:02d}:{best % 60:02d}" if best > 0 else "N/A"))
        layout.addLayout(form)

        by_type = summary.get("by_type", {})
        if by_type:
            layout.addWidget(QLabel("<b>By Type:</b>"))
            for t, count in by_type.items():
                layout.addWidget(QLabel(f"  {t}: {count} solved"))

        layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

# ============================================================================
# LOGIC GRID WIDGET
# ============================================================================

class _GridCell(QFrame):
    """Single clickable cell: empty -> X (no) -> O (yes). Right-click for pencil mark."""
    clicked = Signal()
    right_clicked = Signal()

    def __init__(self, readonly=False, parent=None):
        super().__init__(parent)
        self.readonly = readonly
        self.state = ""
        self.note = ""
        self.setFixedSize(44, 38)
        self.setCursor(Qt.PointingHandCursor if not readonly else Qt.ArrowCursor)
        self._style()

    def _style(self):
        if self.note:
            self.setStyleSheet("background:#f0e6ff; border:2px solid #8e44ad; border-radius:4px;")
        elif self.state == "yes":
            self.setStyleSheet("background:#27ae60; border:1px solid #1e8449; border-radius:4px;")
        elif self.state == "no":
            self.setStyleSheet("background:#e74c3c; border:1px solid #c0392b; border-radius:4px;")
        else:
            self.setStyleSheet("background:#ecf0f1; border:1px solid #bdc3c7; border-radius:4px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        if self.state == "yes":
            painter.setPen(QPen(QColor("white"), 2))
            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "O")
        elif self.state == "no":
            painter.setPen(QPen(QColor("white"), 2))
            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "X")
        elif self.note:
            painter.setPen(QPen(QColor("#8e44ad"), 1))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.note)
        painter.end()

    def set_state(self, s):
        self.state = s
        self._style()

    def set_note(self, n):
        self.note = n
        self._style()

    def mousePressEvent(self, e):
        if self.readonly:
            super().mousePressEvent(e)
            return
        if e.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()
        else:
            self.clicked.emit()
        super().mousePressEvent(e)

class LogicGridWidget(QWidget):
    """Interactive grid for Logic Grid puzzles with pencil marks."""
    state_about_to_change = Signal()

    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.is_preview = False
        self.grid_data = {}
        self.note_data = {}
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self._rebuild()

    def _rebuild(self):
        self._clear_layout(self.main_layout)
        cats = self.puzzle.categories
        if len(cats) < 2:
            lbl = QLabel("Add at least 2 categories to see the grid.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#95a5a6; font-size:14px; padding:40px;")
            self.main_layout.addWidget(lbl)
            return
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setSpacing(0)
        for ci in range(1, len(cats)):
            cat_a, cat_b = cats[0], cats[ci]
            sec = QLabel(f"  {cat_a.name}  x  {cat_b.name}")
            sec.setStyleSheet("font-weight:bold; font-size:13px; color:#2c3e50; padding:8px 0 4px;")
            outer.addWidget(sec)
            grid = QGridLayout()
            grid.setSpacing(2)
            corner = QWidget()
            corner.setFixedSize(100, 28)
            grid.addWidget(corner, 0, 0)
            for j, item in enumerate(cat_b.items):
                h = QLabel(item)
                h.setAlignment(Qt.AlignCenter)
                h.setFixedHeight(28)
                h.setStyleSheet("background:#34495e; color:white; border-radius:3px; font-size:11px; font-weight:bold; padding:2px;")
                h.setWordWrap(True)
                grid.addWidget(h, 0, j + 1)
            for i, item in enumerate(cat_a.items):
                rl = QLabel(item)
                rl.setFixedWidth(96)
                rl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                rl.setStyleSheet("background:#34495e; color:white; border-radius:3px; font-size:11px; font-weight:bold; padding:2px 6px;")
                rl.setWordWrap(True)
                grid.addWidget(rl, i + 1, 0)
                for j in range(len(cat_b.items)):
                    cell = _GridCell(self.is_preview)
                    cell.clicked.connect(lambda r=i, c=ci, it=j: self._click(r, c, it))
                    cell.right_clicked.connect(lambda r=i, c=ci, it=j: self._right_click(r, c, it))
                    st = self.grid_data.get((i, ci, j), "")
                    nt = self.note_data.get((i, ci, j), "")
                    if st:
                        cell.set_state(st)
                    elif nt:
                        cell.set_note(nt)
                    grid.addWidget(cell, i + 1, j + 1)
            outer.addLayout(grid)
            outer.addSpacing(12)
        scroll.setWidget(container)
        self.main_layout.addWidget(scroll)

    def _click(self, row, col_cat, col_item):
        if self.is_preview:
            return
        self.state_about_to_change.emit()
        k = (row, col_cat, col_item)
        cur = self.grid_data.get(k, "")
        self.grid_data[k] = {"": "no", "no": "yes", "yes": ""}[cur]
        self.note_data.pop(k, None)
        self._rebuild()

    def _right_click(self, row, col_cat, col_item):
        if self.is_preview:
            return
        k = (row, col_cat, col_item)
        if self.grid_data.get(k, ""):
            return  # only allow notes on empty cells
        self.state_about_to_change.emit()
        text, ok = _get_text(self, "Pencil Note", "Enter note (short):",
                             self.note_data.get(k, ""))
        if ok:
            if text.strip():
                self.note_data[k] = text.strip()
            else:
                self.note_data.pop(k, None)
            self._rebuild()

    def clear_grid(self):
        self.grid_data.clear()
        self.note_data.clear()
        self._rebuild()

    def get_solution_guess(self):
        guess = {}
        if len(self.puzzle.categories) < 2:
            return guess
        sz = self.puzzle.grid_size()
        for row in range(sz):
            for ci in range(1, len(self.puzzle.categories)):
                for ci2 in range(sz):
                    if self.grid_data.get((row, ci, ci2)) == "yes":
                        guess[ci] = ci2
                        break
        return guess

    def get_state(self):
        return {"grid": dict(self.grid_data), "notes": dict(self.note_data)}

    def set_state(self, s):
        if isinstance(s, dict) and "grid" in s:
            self.grid_data = dict(s["grid"])
            self.note_data = dict(s.get("notes", {}))
        else:
            self.grid_data = dict(s) if isinstance(s, dict) else {}
            self.note_data = {}
        self._rebuild()

    def _clear_layout(self, layout):
        while layout.count():
            c = layout.takeAt(0)
            if c.widget():
                c.widget().deleteLater()
            elif c.layout():
                self._clear_layout(c.layout())


# ============================================================================
# NONOGRAM WIDGET
# ============================================================================

class NonogramCell(QFrame):
    """Nonogram cell: empty/filled/marked."""
    clicked = Signal(int, int, int)

    def __init__(self, row, col, parent=None):
        super().__init__(parent)
        self.row = row
        self.col = col
        self.state = 0
        self.setFixedSize(30, 30)
        self._style()
        self.setCursor(Qt.PointingHandCursor)

    def _style(self):
        if self.state == 1:
            self.setStyleSheet("background:#2c3e50; border:1px solid #1a252f; border-radius:2px;")
        elif self.state == 2:
            self.setStyleSheet("background:#ecf0f1; border:1px solid #bdc3c7; border-radius:2px;")
        else:
            self.setStyleSheet("background:white; border:1px solid #dcdde1; border-radius:2px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.state == 2:
            painter.setPen(QPen(QColor("#e74c3c"), 2))
            r = self.rect().adjusted(6, 6, -6, -6)
            painter.drawLine(r.topLeft(), r.bottomRight())
            painter.drawLine(r.topRight(), r.bottomLeft())
        painter.end()

    def mousePressEvent(self, e):
        btn = 1 if e.button() == Qt.MouseButton.LeftButton else 2
        self.clicked.emit(self.row, self.col, btn)

class NonogramWidget(QWidget):
    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.grid = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        if not self.puzzle.row_clues or not self.puzzle.col_clues:
            layout.addWidget(QLabel("No clue data. Generate or load a puzzle."))
            return
        max_rc = max(len(c) for c in self.puzzle.row_clues)
        max_cc = max(len(c) for c in self.puzzle.col_clues)
        ctrl = QHBoxLayout()
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self.clear_all)
        clear_btn.setFixedHeight(30)
        ctrl.addWidget(clear_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)
        grid = QGridLayout()
        grid.setSpacing(1)
        empty_tl = QWidget()
        empty_tl.setFixedSize(max_rc * 22, max_cc * 18)
        grid.addWidget(empty_tl, 0, 0)
        for j, clues in enumerate(self.puzzle.col_clues):
            col_w = QWidget()
            col_l = QVBoxLayout(col_w)
            col_l.setContentsMargins(0, 0, 0, 2)
            col_l.setSpacing(0)
            for _ in range(max_cc - len(clues)):
                col_l.addStretch()
            for c in clues:
                lbl = QLabel(str(c))
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFixedHeight(18)
                lbl.setStyleSheet("font-size:11px; font-weight:bold; color:#2c3e50;")
                col_l.addWidget(lbl)
            grid.addWidget(col_w, 0, j + 1)
        self.grid = []
        for i, clues in enumerate(self.puzzle.row_clues):
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(2, 0, 0, 0)
            row_l.setSpacing(0)
            for _ in range(max_rc - len(clues)):
                sp = QLabel("")
                sp.setFixedWidth(22)
                row_l.addWidget(sp)
            for c in clues:
                lbl = QLabel(str(c))
                lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                lbl.setFixedWidth(22)
                lbl.setStyleSheet("font-size:11px; font-weight:bold; color:#2c3e50;")
                row_l.addWidget(lbl)
            grid.addWidget(row_w, i + 1, 0)
            row_cells = []
            for j in range(self.puzzle.width):
                cell = NonogramCell(i, j)
                cell.clicked.connect(self._cell_click)
                grid.addWidget(cell, i + 1, j + 1)
                row_cells.append(cell)
            self.grid.append(row_cells)
        layout.addLayout(grid)
        legend = QLabel("Left-click: Fill  |  Right-click: Mark X  |  Click again to clear")
        legend.setAlignment(Qt.AlignCenter)
        legend.setStyleSheet("color:#95a5a6; font-size:11px; padding:4px;")
        layout.addWidget(legend)

    def _cell_click(self, r, c, btn):
        cell = self.grid[r][c]
        if btn == 1:
            cell.state = 0 if cell.state == 1 else 1
        else:
            cell.state = 0 if cell.state == 2 else 2
        cell._style()
        cell.update()

    def clear_all(self):
        for row in self.grid:
            for cell in row:
                cell.state = 0
                cell._style()
                cell.update()

    def get_state(self):
        return [[self.grid[i][j].state for j in range(len(self.grid[i]))] for i in range(len(self.grid))]

    def set_state(self, state):
        for i in range(min(len(state), len(self.grid))):
            for j in range(min(len(state[i]), len(self.grid[i]))):
                self.grid[i][j].state = state[i][j]
                self.grid[i][j]._style()
                self.grid[i][j].update()

    def check_solution(self):
        if not self.puzzle.solution:
            return False, "No solution set."
        errors = 0
        for i in range(min(len(self.grid), len(self.puzzle.solution))):
            for j in range(min(len(self.grid[i]), len(self.puzzle.solution[i]))):
                actual = 1 if self.grid[i][j].state == 1 else 0
                if actual != self.puzzle.solution[i][j]:
                    errors += 1
        if errors == 0:
            return True, "Correct! The picture is complete!"
        return False, f"{errors} cells are incorrect."

    def get_progress(self):
        if not self.puzzle.solution:
            return 0.0
        total = sum(sum(row) for row in self.puzzle.solution)
        if total == 0:
            return 1.0
        filled = sum(1 for i in range(min(len(self.grid), len(self.puzzle.solution)))
                     for j in range(min(len(self.grid[i]), len(self.puzzle.solution[i])))
                     if self.grid[i][j].state == 1 and self.puzzle.solution[i][j] == 1)
        return filled / total

    def give_hint(self):
        if not self.puzzle.solution:
            return None
        cands = []
        for i in range(min(len(self.grid), len(self.puzzle.solution))):
            for j in range(min(len(self.grid[i]), len(self.puzzle.solution[i]))):
                should = self.puzzle.solution[i][j] == 1
                is_f = self.grid[i][j].state == 1
                if should != is_f:
                    cands.append((i, j))
        if not cands:
            return None
        r, c = random.choice(cands)
        self.grid[r][c].state = self.puzzle.solution[r][c]
        self.grid[r][c]._style()
        self.grid[r][c].update()
        return (r, c)


# ============================================================================
# WORD LOGIC WIDGET
# ============================================================================

class WordLogicWidget(QWidget):
    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.guess = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        if not self.puzzle.variables:
            layout.addWidget(QLabel("No variables defined."))
            return
        if self.puzzle.clues:
            clue_box = QGroupBox("Clues")
            clue_lay = QVBoxLayout(clue_box)
            for i, clue in enumerate(self.puzzle.clues, 1):
                lbl = QLabel(f"<b>{i}.</b> {clue}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet("padding:2px 0;")
                clue_lay.addWidget(lbl)
            layout.addWidget(clue_box)
        grid_group = QGroupBox("Your Solution")
        grid_lay = QVBoxLayout(grid_group)
        self.sol_combos = {}
        for var in self.puzzle.variables:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{var['name']}:</b>"))
            combo = QComboBox()
            combo.addItem("-- ? --")
            for val in var["domain"]:
                combo.addItem(val)
            if var["name"] in self.guess:
                idx = var["domain"].index(self.guess[var["name"]]) + 1
                combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(
                lambda idx, name=var["name"], domain=var["domain"]: self._combo_changed(idx, name, domain))
            row.addWidget(combo, 1)
            grid_lay.addLayout(row)
            self.sol_combos[var["name"]] = combo
        layout.addWidget(grid_group, 1)

    def _combo_changed(self, idx, name, domain):
        if idx > 0:
            self.guess[name] = domain[idx - 1]
        else:
            self.guess.pop(name, None)

    def check_solution(self):
        if not self.puzzle.solution:
            return False, "No solution set."
        details = []
        correct = True
        for var in self.puzzle.variables:
            name = var["name"]
            guessed = self.guess.get(name)
            actual = self.puzzle.solution.get(name)
            if not guessed:
                details.append(f"? {name}: not answered")
                correct = False
            elif guessed == actual:
                details.append(f"+ {name}: {guessed} - correct!")
            else:
                details.append(f"x {name}: you said '{guessed}', correct is '{actual}'")
                correct = False
        msg = "Correct!\n" if correct else "Not quite...\n"
        return correct, msg + "\n".join(details)

    def give_hint(self):
        for var in self.puzzle.variables:
            name = var["name"]
            if name not in self.guess or self.guess[name] != self.puzzle.solution.get(name):
                self.guess[name] = self.puzzle.solution[name]
                combo = self.sol_combos.get(name)
                if combo and self.puzzle.solution[name] in var["domain"]:
                    idx = var["domain"].index(self.puzzle.solution[name]) + 1
                    combo.setCurrentIndex(idx)
                return name
        return None

    def get_progress(self):
        if not self.puzzle.variables:
            return 0.0
        answered = sum(1 for v in self.puzzle.variables if v["name"] in self.guess)
        return answered / len(self.puzzle.variables)

    def get_state(self):
        return dict(self.guess)

    def set_state(self, state):
        self.guess = dict(state)
        for name, combo in self.sol_combos.items():
            var = next((v for v in self.puzzle.variables if v["name"] == name), None)
            if var and name in self.guess and self.guess[name] in var["domain"]:
                idx = var["domain"].index(self.guess[name]) + 1
                combo.setCurrentIndex(idx)

# ============================================================================
# KAKURO WIDGET
# ============================================================================

class KakuroCell(QFrame):
    """Kakuro cell: black, clue, or editable number."""
    valueChanged = Signal(int, int, int)

    def __init__(self, row, col, cell_type=0, row_sum=None, col_sum=None, parent=None):
        super().__init__(parent)
        self.row = row
        self.col = col
        self.cell_type = cell_type  # 0=black, 1=clue, 2=editable
        self.row_sum = row_sum
        self.col_sum = col_sum
        self.value = 0
        self.setFixedSize(42, 42)
        self._style()
        if cell_type == 2:
            self.setCursor(Qt.PointingHandCursor)

    def _style(self):
        if self.cell_type == 0:
            self.setStyleSheet("background:#34495e; border:1px solid #2c3e50;")
        elif self.cell_type == 1:
            self.setStyleSheet("background:#dfe6e9; border:1px solid #bdc3c7;")
        else:
            if self.value > 0:
                self.setStyleSheet("background:white; border:2px solid #3498db; border-radius:3px;")
            else:
                self.setStyleSheet("background:white; border:1px solid #bdc3c7; border-radius:3px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        if self.cell_type == 0:
            painter.end()
            return
        if self.cell_type == 1:
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QPen(QColor("#2c3e50"), 1))
            if self.row_sum is not None:
                painter.drawText(rect.adjusted(2, 2, 0, rect.height() // 2),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                                 str(self.row_sum))
            if self.col_sum is not None:
                painter.drawText(rect.adjusted(0, rect.height() // 2, -2, -2),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                                 str(self.col_sum))
        elif self.cell_type == 2 and self.value > 0:
            painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
            painter.setPen(QPen(QColor("#2c3e50"), 1))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self.value))
        painter.end()

    def mousePressEvent(self, e):
        if self.cell_type == 2:
            self.valueChanged.emit(self.row, self.col, 0)
        super().mousePressEvent(e)

    def set_value(self, v):
        self.value = v
        self._style()
        self.update()

class KakuroWidget(QWidget):
    """Interactive Kakuro grid with clue cells and number entry."""
    state_about_to_change = Signal()

    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.cells = []
        self.selected = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        if not self.puzzle.layout:
            layout.addWidget(QLabel("No Kakuro data. Generate or load a puzzle."))
            return
        grid = QGridLayout()
        grid.setSpacing(1)
        self.cells = []
        for r in range(self.puzzle.rows):
            row_cells = []
            for c in range(self.puzzle.cols):
                ct = self.puzzle.layout[r][c] if r < len(self.puzzle.layout) and c < len(self.puzzle.layout[0]) else 0
                rs = self.puzzle.row_sums.get((r, c))
                cs = self.puzzle.col_sums.get((r, c))
                cell = KakuroCell(r, c, ct, rs, cs)
                if ct == 2:
                    cell.valueChanged.connect(self._select)
                    if (r < len(self.puzzle.solution) and c < len(self.puzzle.solution[0])
                            and self.puzzle.solution[r][c] > 0):
                        pass  # don't reveal solution
                grid.addWidget(cell, r, c)
                row_cells.append(cell)
            self.cells.append(row_cells)
        layout.addLayout(grid)
        # Number pad
        pad = QHBoxLayout()
        for n in range(1, 10):
            btn = QPushButton(str(n))
            btn.setFixedSize(38, 34)
            btn.setFont(QFont("Segoe UI", 13, QFont.Bold))
            btn.clicked.connect(lambda checked, num=n: self._enter(num))
            pad.addWidget(btn)
        erase = QPushButton("X")
        erase.setFixedSize(38, 34)
        erase.setStyleSheet("background:#e74c3c;")
        erase.clicked.connect(self._erase)
        pad.addWidget(erase)
        layout.addLayout(pad)
        legend = QLabel("Click a cell, then type a number (1-9). Each run must have unique digits.")
        legend.setAlignment(Qt.AlignCenter)
        legend.setStyleSheet("color:#95a5a6; font-size:11px; padding:4px;")
        layout.addWidget(legend)

    def _select(self, r, c):
        self.selected = (r, c)

    def _enter(self, n):
        if not self.selected:
            return
        r, c = self.selected
        if 0 <= r < len(self.cells) and 0 <= c < len(self.cells[0]):
            self.state_about_to_change.emit()
            self.cells[r][c].set_value(n)

    def _erase(self):
        if not self.selected:
            return
        r, c = self.selected
        if 0 <= r < len(self.cells) and 0 <= c < len(self.cells[0]):
            self.state_about_to_change.emit()
            self.cells[r][c].set_value(0)

    def get_state(self):
        return [[self.cells[r][c].value if self.cells[r][c].cell_type == 2 else 0
                 for c in range(len(self.cells[0]))] for r in range(len(self.cells))]

    def set_state(self, state):
        for r in range(min(len(state), len(self.cells))):
            for c in range(min(len(state[r]), len(self.cells[0]))):
                if self.cells[r][c].cell_type == 2:
                    self.cells[r][c].set_value(state[r][c])

    def check_solution(self):
        if not self.puzzle.solution:
            return False, "No solution set."
        errors = 0
        empty = 0
        for r in range(min(len(self.cells), len(self.puzzle.solution))):
            for c in range(min(len(self.cells[0]), len(self.puzzle.solution[0]))):
                if self.cells[r][c].cell_type == 2:
                    v = self.cells[r][c].value
                    sv = self.puzzle.solution[r][c] if r < len(self.puzzle.solution) and c < len(self.puzzle.solution[0]) else 0
                    if v == 0:
                        empty += 1
                    elif v != sv:
                        errors += 1
        if empty > 0:
            return False, f"{empty} cells still empty."
        if errors > 0:
            return False, f"{errors} incorrect cells."
        return True, "Correct! Kakuro solved!"

    def get_progress(self):
        if not self.puzzle.solution:
            return 0.0
        total = sum(1 for r in range(len(self.cells)) for c in range(len(self.cells[0]))
                    if self.cells[r][c].cell_type == 2)
        if total == 0:
            return 1.0
        filled = sum(1 for r in range(len(self.cells)) for c in range(len(self.cells[0]))
                     if self.cells[r][c].cell_type == 2 and self.cells[r][c].value > 0)
        return filled / total

    def give_hint(self):
        if not self.puzzle.solution:
            return None
        cands = []
        for r in range(min(len(self.cells), len(self.puzzle.solution))):
            for c in range(min(len(self.cells[0]), len(self.puzzle.solution[0]))):
                if self.cells[r][c].cell_type == 2:
                    sv = self.puzzle.solution[r][c]
                    if self.cells[r][c].value != sv:
                        cands.append((r, c, sv))
        if not cands:
            return None
        r, c, v = random.choice(cands)
        self.cells[r][c].set_value(v)
        return (r, c, v)


# ============================================================================
# WORD SEARCH WIDGET
# ============================================================================

class WSCell(QFrame):
    """Word Search cell."""
    clicked = Signal(int, int)

    def __init__(self, row, col, letter="", parent=None):
        super().__init__(parent)
        self.row = row
        self.col = col
        self.letter = letter
        self.found = False
        self.selecting = False
        self.setFixedSize(32, 32)
        self._style()
        self.setCursor(Qt.PointingHandCursor)

    def _style(self):
        if self.found:
            self.setStyleSheet("background:#27ae60; border:1px solid #1e8449; border-radius:2px;")
        elif self.selecting:
            self.setStyleSheet("background:#3498db; border:1px solid #2980b9; border-radius:2px;")
        else:
            self.setStyleSheet("background:white; border:1px solid #dcdde1; border-radius:2px;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("white") if self.found or self.selecting else QColor("#2c3e50")
        painter.setPen(QPen(color, 1))
        painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.letter)
        painter.end()

    def mousePressEvent(self, e):
        self.clicked.emit(self.row, self.col)

class WordSearchWidget(QWidget):
    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.cells = []
        self.found_words = set()
        self.selecting = False
        self.sel_start = None
        self.sel_cells = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        if not self.puzzle.grid:
            layout.addWidget(QLabel("No word search data."))
            return
        # Word list
        word_box = QGroupBox("Words to Find")
        wl = QVBoxLayout(word_box)
        self.word_labels = {}
        for w in self.puzzle.words:
            lbl = QLabel(w)
            lbl.setStyleSheet("font-size:13px; font-family:monospace; padding:1px 4px;")
            if w in self.found_words:
                lbl.setStyleSheet("font-size:13px; font-family:monospace; padding:1px 4px; color:#27ae60; text-decoration:line-through;")
            wl.addWidget(lbl)
            self.word_labels[w] = lbl
        layout.addWidget(word_box)
        # Grid
        grid = QGridLayout()
        grid.setSpacing(1)
        self.cells = []
        for r in range(self.puzzle.height):
            row_cells = []
            for c in range(self.puzzle.width):
                letter = self.puzzle.grid[r][c] if r < len(self.puzzle.grid) and c < len(self.puzzle.grid[0]) else ""
                cell = WSCell(r, c, letter)
                cell.clicked.connect(self._cell_click)
                grid.addWidget(cell, r, c)
                row_cells.append(cell)
            self.cells.append(row_cells)
        layout.addLayout(grid)
        self.found_label = QLabel(f"Found: 0 / {len(self.puzzle.words)}")
        self.found_label.setAlignment(Qt.AlignCenter)
        self.found_label.setStyleSheet("font-weight:bold; color:#2c3e50; padding:4px;")
        layout.addWidget(self.found_label)

    def _cell_click(self, r, c):
        if not self.selecting:
            self.selecting = True
            self.sel_start = (r, c)
            self._clear_selection()
            self.cells[r][c].selecting = True
            self.cells[r][c]._style()
            self.cells[r][c].update()
            self.sel_cells = [(r, c)]
        else:
            # Check if this completes a valid selection
            self._clear_selection()
            self.selecting = False
            sr, sc = self.sel_start
            dr = 0 if r == sr else (1 if r > sr else -1)
            dc = 0 if c == sc else (1 if c > sc else -1)
            # Must be a straight line
            if dr == 0 and dc == 0:
                return
            if dr != 0 and dc != 0 and abs(r - sr) != abs(c - sc):
                return
            # Extract word along this line
            word = ""
            cells = []
            cr, cc = sr, sc
            while 0 <= cr < self.puzzle.height and 0 <= cc < self.puzzle.width:
                cells.append((cr, cc))
                word += self.puzzle.grid[cr][cc]
                if cr == r and cc == c:
                    break
                cr += dr
                cc += dc
            # Check forward and reverse
            for w in [word, word[::-1]]:
                if w in self.puzzle.words and w not in self.found_words:
                    self.found_words.add(w)
                    for cr2, cc2 in cells:
                        self.cells[cr2][cc2].found = True
                        self.cells[cr2][cc2]._style()
                        self.cells[cr2][cc2].update()
                    if w in self.word_labels:
                        self.word_labels[w].setStyleSheet(
                            "font-size:13px; font-family:monospace; padding:1px 4px; color:#27ae60; text-decoration:line-through;")
                    self.found_label.setText(f"Found: {len(self.found_words)} / {len(self.puzzle.words)}")
                    break

    def _clear_selection(self):
        for r, c in self.sel_cells:
            if 0 <= r < len(self.cells) and 0 <= c < len(self.cells[0]):
                self.cells[r][c].selecting = False
                self.cells[r][c]._style()
                self.cells[r][c].update()
        self.sel_cells = []

    def get_state(self):
        return list(self.found_words)

    def set_state(self, state):
        self.found_words = set(state) if isinstance(state, list) else set()
        for w in self.found_words:
            if w in self.word_labels:
                self.word_labels[w].setStyleSheet(
                    "font-size:13px; font-family:monospace; padding:1px 4px; color:#27ae60; text-decoration:line-through;")
        # Mark cells as found
        for pl in self.puzzle.placements:
            if pl["word"] in self.found_words:
                for i in range(len(pl["word"])):
                    r = pl["r"] + pl["dr"] * i
                    c = pl["c"] + pl["dc"] * i
                    if 0 <= r < len(self.cells) and 0 <= c < len(self.cells[0]):
                        self.cells[r][c].found = True
                        self.cells[r][c]._style()
                        self.cells[r][c].update()
        self.found_label.setText(f"Found: {len(self.found_words)} / {len(self.puzzle.words)}")

    def check_solution(self):
        remaining = [w for w in self.puzzle.words if w not in self.found_words]
        if not remaining:
            return True, "All words found!"
        return False, f"{len(remaining)} words remaining: {', '.join(remaining)}"

    def get_progress(self):
        if not self.puzzle.words:
            return 1.0
        return len(self.found_words) / len(self.puzzle.words)

    def give_hint(self):
        remaining = [pl for pl in self.puzzle.placements if pl["word"] not in self.found_words]
        if not remaining:
            return None
        pl = random.choice(remaining)
        self.found_words.add(pl["word"])
        for i in range(len(pl["word"])):
            r = pl["r"] + pl["dr"] * i
            c = pl["c"] + pl["dc"] * i
            if 0 <= r < len(self.cells) and 0 <= c < len(self.cells[0]):
                self.cells[r][c].found = True
                self.cells[r][c]._style()
                self.cells[r][c].update()
        if pl["word"] in self.word_labels:
            self.word_labels[pl["word"]].setStyleSheet(
                "font-size:13px; font-family:monospace; padding:1px 4px; color:#27ae60; text-decoration:line-through;")
        self.found_label.setText(f"Found: {len(self.found_words)} / {len(self.puzzle.words)}")
        return pl["word"]

# ============================================================================
# PUZZLE TAB
# ============================================================================

class PuzzleTab(QWidget):
    """One tab = one puzzle with its editor panel and grid widget."""
    def __init__(self, puzzle, parent=None):
        super().__init__(parent)
        self.puzzle = puzzle
        self.undo_stack = UndoRedoStack()
        self.grid_widget = None
        self.editor_panel = None
        self.hints_used = 0
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(6)
        self.editor_panel = self._make_editor()
        self.editor_panel.setFixedWidth(340)
        layout.addWidget(self.editor_panel)
        self.grid_widget = self._make_grid()
        layout.addWidget(self.grid_widget, 1)

    def _make_editor(self):
        t = type(self.puzzle).type_name
        if t == "Logic Grid":
            return _LogicGridEditor(self)
        elif t == "Nonogram":
            return _NonogramEditor(self)
        elif t == "Word Logic":
            return _WordLogicEditorPanel(self)
        elif t == "Kakuro":
            return _KakuroEditor(self)
        elif t == "Word Search":
            return _WordSearchEditor(self)
        return QLabel("No editor for this type.")

    def _make_grid(self):
        t = type(self.puzzle).type_name
        if t == "Logic Grid":
            w = LogicGridWidget(self.puzzle)
            w.state_about_to_change.connect(self.save_undo_state)
            return w
        elif t == "Nonogram":
            return NonogramWidget(self.puzzle)
        elif t == "Word Logic":
            return WordLogicWidget(self.puzzle)
        elif t == "Kakuro":
            w = KakuroWidget(self.puzzle)
            w.state_about_to_change.connect(self.save_undo_state)
            return w
        elif t == "Word Search":
            return WordSearchWidget(self.puzzle)
        return QLabel("No grid for this type.")

    def save_undo_state(self):
        if hasattr(self.grid_widget, "get_state"):
            self.undo_stack.push(self.grid_widget.get_state())

    def undo(self):
        if hasattr(self.grid_widget, "get_state") and hasattr(self.grid_widget, "set_state"):
            state = self.undo_stack.undo(self.grid_widget.get_state())
            if state is not None:
                self.grid_widget.set_state(state)

    def redo(self):
        if hasattr(self.grid_widget, "get_state") and hasattr(self.grid_widget, "set_state"):
            state = self.undo_stack.redo(self.grid_widget.get_state())
            if state is not None:
                self.grid_widget.set_state(state)

    def get_progress(self):
        if hasattr(self.grid_widget, "get_progress"):
            return self.grid_widget.get_progress()
        return 0.0

    def check(self):
        if hasattr(self.grid_widget, "check_solution"):
            return self.grid_widget.check_solution()
        return False, "No checker for this type."

    def give_hint(self):
        if hasattr(self.grid_widget, "give_hint"):
            self.hints_used += 1
            return self.grid_widget.give_hint()
        return None

    def clear_grid(self):
        if hasattr(self.grid_widget, "clear_grid"):
            self.grid_widget.clear_grid()
        elif hasattr(self.grid_widget, "clear_all"):
            self.grid_widget.clear_all()

    def rebuild(self):
        old_state = None
        if self.grid_widget and hasattr(self.grid_widget, "get_state"):
            old_state = self.grid_widget.get_state()
        self.grid_widget.deleteLater()
        self.grid_widget = self._make_grid()
        self.layout().addWidget(self.grid_widget, 1)
        if old_state and hasattr(self.grid_widget, "set_state"):
            self.grid_widget.set_state(old_state)


# ============================================================================
# EDITOR PANELS
# ============================================================================

class _DraggableClueList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        if hasattr(self, "_on_reorder"):
            self._on_reorder()

class _LogicGridEditor(QWidget):
    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.puzzle = tab.puzzle
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget()
        # Categories tab
        cat_w = QWidget()
        cat_l = QVBoxLayout(cat_w)
        cat_l.setContentsMargins(6, 6, 6, 6)
        self.cat_list = QListWidget()
        self.cat_list.currentRowChanged.connect(self._on_cat_sel)
        cat_l.addWidget(QLabel("Categories:"))
        cat_l.addWidget(self.cat_list)
        btns = QHBoxLayout()
        for txt, fn in [("+ Add", self._add_cat), ("Edit", self._edit_cat), ("Remove", self._del_cat)]:
            b = QPushButton(txt)
            if txt == "Remove":
                b.setObjectName("danger")
            b.clicked.connect(fn)
            btns.addWidget(b)
        cat_l.addLayout(btns)
        self.cat_detail = QLabel("Select a category.")
        self.cat_detail.setWordWrap(True)
        self.cat_detail.setStyleSheet("padding:8px; border:1px solid #dcdde1; border-radius:4px; min-height:60px;")
        cat_l.addWidget(self.cat_detail)
        cat_l.addStretch()
        tabs.addTab(cat_w, "Categories")
        # Clues tab with drag-drop
        clu_w = QWidget()
        clu_l = QVBoxLayout(clu_w)
        clu_l.setContentsMargins(6, 6, 6, 6)
        self.clue_list = _DraggableClueList()
        self.clue_list._on_reorder = self._clues_reordered
        self.clue_list.currentRowChanged.connect(self._on_clue_sel)
        clu_l.addWidget(QLabel("Clues (drag to reorder):"))
        clu_l.addWidget(self.clue_list)
        btns2 = QHBoxLayout()
        for txt, fn in [("+ Add", self._add_clue), ("Edit", self._edit_clue), ("Remove", self._del_clue)]:
            b = QPushButton(txt)
            if txt == "Remove":
                b.setObjectName("danger")
            b.clicked.connect(fn)
            btns2.addWidget(b)
        clu_l.addLayout(btns2)
        self.clue_edit = QTextEdit()
        self.clue_edit.setMaximumHeight(80)
        self.clue_edit.setPlaceholderText("Type clue here...")
        self.clue_edit.textChanged.connect(self._clue_text_changed)
        clu_l.addWidget(self.clue_edit)
        reorder = QHBoxLayout()
        up = QPushButton("Up")
        down = QPushButton("Down")
        up.clicked.connect(self._move_up)
        down.clicked.connect(self._move_down)
        reorder.addWidget(up)
        reorder.addWidget(down)
        reorder.addStretch()
        clu_l.addLayout(reorder)
        tabs.addTab(clu_w, "Clues")
        layout.addWidget(tabs)
        # Tools
        tools = QGroupBox("Tools")
        tl = QVBoxLayout(tools)
        auto_clue_btn = QPushButton("Auto-Generate Clues")
        auto_clue_btn.clicked.connect(self._auto_clues)
        tl.addWidget(auto_clue_btn)
        solve_btn = QPushButton("Auto-Solve")
        solve_btn.setObjectName("success")
        solve_btn.clicked.connect(self._auto_solve)
        tl.addWidget(solve_btn)
        score_btn = QPushButton("Score Difficulty")
        score_btn.clicked.connect(self._score)
        tl.addWidget(score_btn)
        layout.addWidget(tools)
        self._refresh_cats()
        self._refresh_clues()

    def _refresh_cats(self):
        self.cat_list.blockSignals(True)
        self.cat_list.clear()
        for c in self.puzzle.categories:
            self.cat_list.addItem(f"{c.name} ({len(c.items)})")
        self.cat_list.blockSignals(False)

    def _on_cat_sel(self, row):
        if 0 <= row < len(self.puzzle.categories):
            c = self.puzzle.categories[row]
            self.cat_detail.setText(f"<b>{c.name}</b><br>" + "<br>".join(f"- {i}" for i in c.items))
        else:
            self.cat_detail.setText("Select a category.")

    def _add_cat(self):
        req = self.puzzle.grid_size() if self.puzzle.categories else 0
        dlg = CategoryDialog(self, required_size=req)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.category:
            self.puzzle.add_category(dlg.category)
            self._refresh_cats()
            self.tab.rebuild()
            self.cat_list.setCurrentRow(len(self.puzzle.categories) - 1)

    def _edit_cat(self):
        r = self.cat_list.currentRow()
        if r < 0:
            return
        dlg = CategoryDialog(self, category=self.puzzle.categories[r], required_size=self.puzzle.grid_size())
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.category:
            self.puzzle.categories[r] = dlg.category
            self._refresh_cats()
            self.cat_list.setCurrentRow(r)
            self.tab.rebuild()

    def _del_cat(self):
        r = self.cat_list.currentRow()
        if r < 0:
            return
        self.puzzle.remove_category(r)
        self._refresh_cats()
        self.tab.rebuild()

    def _refresh_clues(self):
        self.clue_list.blockSignals(True)
        cur = self.clue_list.currentRow()
        self.clue_list.clear()
        for i, c in enumerate(self.puzzle.clues):
            self.clue_list.addItem(f"{i + 1}. {c[:50]}{'...' if len(c) > 50 else ''}")
        if 0 <= cur < len(self.puzzle.clues):
            self.clue_list.setCurrentRow(cur)
        self.clue_list.blockSignals(False)

    def _on_clue_sel(self, row):
        self.clue_edit.blockSignals(True)
        if 0 <= row < len(self.puzzle.clues):
            self.clue_edit.setPlainText(self.puzzle.clues[row])
        else:
            self.clue_edit.clear()
        self.clue_edit.blockSignals(False)

    def _clue_text_changed(self):
        r = self.clue_list.currentRow()
        if 0 <= r < len(self.puzzle.clues):
            self.puzzle.clues[r] = self.clue_edit.toPlainText()
            self._refresh_clues()

    def _add_clue(self):
        self.puzzle.clues.append("Enter clue...")
        self._refresh_clues()
        self.clue_list.setCurrentRow(len(self.puzzle.clues) - 1)
        self.clue_edit.setFocus()
        self.clue_edit.selectAll()

    def _edit_clue(self):
        self.clue_edit.setFocus()

    def _del_clue(self):
        r = self.clue_list.currentRow()
        if r >= 0:
            self.puzzle.clues.pop(r)
            self._refresh_clues()

    def _move_up(self):
        r = self.clue_list.currentRow()
        if r > 0:
            self.puzzle.clues[r], self.puzzle.clues[r - 1] = self.puzzle.clues[r - 1], self.puzzle.clues[r]
            self._refresh_clues()
            self.clue_list.setCurrentRow(r - 1)

    def _move_down(self):
        r = self.clue_list.currentRow()
        if 0 <= r < len(self.puzzle.clues) - 1:
            self.puzzle.clues[r], self.puzzle.clues[r + 1] = self.puzzle.clues[r + 1], self.puzzle.clues[r]
            self._refresh_clues()
            self.clue_list.setCurrentRow(r + 1)

    def _clues_reordered(self):
        new_clues = []
        for i in range(self.clue_list.count()):
            item = self.clue_list.item(i)
            # Extract clue text (strip number prefix)
            text = item.text()
            if ". " in text:
                text = text.split(". ", 1)[1]
            new_clues.append(text)
        self.puzzle.clues = new_clues
        self._refresh_clues()

    def _auto_clues(self):
        if not self.puzzle.solution:
            QMessageBox.warning(self, "No Solution", "Set a solution first (Edit > Set Solution).")
            return
        self.puzzle.clues = AutoClueGenerator.generate(self.puzzle, self.puzzle.difficulty)
        self._refresh_clues()
        QMessageBox.information(self, "Done", f"Generated {len(self.puzzle.clues)} clues.")

    def _auto_solve(self):
        result = LogicGridSolver.solve(self.puzzle)
        if result is None:
            QMessageBox.information(self, "Solver", "Could not find a solution with current clues.")
        else:
            # Apply solution to grid
            cats = self.puzzle.categories
            sz = self.puzzle.grid_size()
            gw = self.tab.grid_widget
            gw.grid_data.clear()
            for ci in range(1, len(cats)):
                if ci in result:
                    perm = result[ci]
                    for ri in range(sz):
                        gw.grid_data[(ri, ci, perm[ri])] = "yes"
                        for other in range(sz):
                            if other != perm[ri]:
                                gw.grid_data[(ri, ci, other)] = "no"
            gw._rebuild()
            QMessageBox.information(self, "Solved", "Auto-solved! Grid filled.")

    def _score(self):
        score = DifficultyScorer.score(self.puzzle)
        QMessageBox.information(self, "Difficulty Score",
            f"Score: {score}/100\n"
            f"{'Easy (10-33)' if score < 34 else 'Medium (34-66)' if score < 67 else 'Hard (67-100)'}")

class _NonogramEditor(QWidget):
    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.puzzle = tab.puzzle
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        info = QGroupBox("Info")
        il = QFormLayout(info)
        il.addRow("Size:", QLabel(f"{self.puzzle.width}x{self.puzzle.height}"))
        il.addRow("Difficulty:", QLabel(self.puzzle.difficulty))
        sc = DifficultyScorer.score(self.puzzle)
        il.addRow("Score:", QLabel(f"{sc}/100"))
        layout.addWidget(info)
        b = QPushButton("Generate New Nonogram")
        b.clicked.connect(self._regen)
        layout.addWidget(b)
        layout.addStretch()

    def _regen(self):
        dlg = NewPuzzleDialog(self)
        dlg.chosen_type = "Nonogram"
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pp = dlg.puzzle_params
            np = NonogramEngine.generate(pp.get("width", 10), pp.get("height", 10), difficulty=dlg.chosen_difficulty)
            self.tab.puzzle = np
            self._rebuild_tab(np)

    def _rebuild_tab(self, new_puzzle):
        self.tab.undo_stack.clear()
        self.tab.grid_widget.deleteLater()
        self.tab.grid_widget = NonogramWidget(new_puzzle, self.tab)
        self.tab.layout().addWidget(self.tab.grid_widget, 1)
        self.tab.editor_panel.deleteLater()
        self.tab.editor_panel = _NonogramEditor(self.tab)
        self.tab.editor_panel.setFixedWidth(340)
        self.tab.layout().insertWidget(0, self.tab.editor_panel)

class _WordLogicEditorPanel(QWidget):
    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.puzzle = tab.puzzle
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        info = QGroupBox("Variables")
        il = QVBoxLayout(info)
        for v in self.puzzle.variables:
            il.addWidget(QLabel(f"<b>{v['name']}:</b> {', '.join(v['domain'])}"))
        layout.addWidget(info)
        eb = QPushButton("Edit Variables & Constraints")
        eb.clicked.connect(self._edit)
        gb = QPushButton("Generate New Word Logic")
        gb.clicked.connect(self._regen)
        layout.addWidget(eb)
        layout.addWidget(gb)
        layout.addStretch()

    def _edit(self):
        dlg = WordLogicEditorDialog(self.puzzle, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.tab.rebuild()

    def _regen(self):
        np = WordLogicGenerator.generate(difficulty=self.puzzle.difficulty)
        self.tab.puzzle = np
        self.tab.undo_stack.clear()
        self.tab.grid_widget.deleteLater()
        self.tab.grid_widget = WordLogicWidget(np, self.tab)
        self.tab.layout().addWidget(self.tab.grid_widget, 1)
        self.tab.editor_panel.deleteLater()
        self.tab.editor_panel = _WordLogicEditorPanel(self.tab)
        self.tab.editor_panel.setFixedWidth(340)
        self.tab.layout().insertWidget(0, self.tab.editor_panel)

class _KakuroEditor(QWidget):
    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.puzzle = tab.puzzle
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        info = QGroupBox("Info")
        il = QFormLayout(info)
        il.addRow("Size:", QLabel(f"{self.puzzle.rows}x{self.puzzle.cols}"))
        il.addRow("Difficulty:", QLabel(self.puzzle.difficulty))
        il.addRow("Row Clues:", QLabel(str(len(self.puzzle.row_sums))))
        il.addRow("Col Clues:", QLabel(str(len(self.puzzle.col_sums))))
        layout.addWidget(info)
        b = QPushButton("Generate New Kakuro")
        b.clicked.connect(self._regen)
        layout.addWidget(b)
        layout.addStretch()

    def _regen(self):
        dlg = NewPuzzleDialog(self)
        dlg.chosen_type = "Kakuro"
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pp = dlg.puzzle_params
            np = KakuroEngine.generate(pp.get("width", 8), pp.get("height", 8), difficulty=dlg.chosen_difficulty)
            self.tab.puzzle = np
            self.tab.undo_stack.clear()
            self.tab.grid_widget.deleteLater()
            self.tab.grid_widget = KakuroWidget(np, self.tab)
            self.tab.layout().addWidget(self.tab.grid_widget, 1)
            self.tab.editor_panel.deleteLater()
            self.tab.editor_panel = _KakuroEditor(self.tab)
            self.tab.editor_panel.setFixedWidth(340)
            self.tab.layout().insertWidget(0, self.tab.editor_panel)

class _WordSearchEditor(QWidget):
    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.puzzle = tab.puzzle
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        info = QGroupBox("Info")
        il = QFormLayout(info)
        il.addRow("Size:", QLabel(f"{self.puzzle.width}x{self.puzzle.height}"))
        il.addRow("Words:", QLabel(str(len(self.puzzle.words))))
        il.addRow("Difficulty:", QLabel(self.puzzle.difficulty))
        layout.addWidget(info)
        # Word list
        wl = QGroupBox("Words")
        wll = QVBoxLayout(wl)
        for w in self.puzzle.words:
            wll.addWidget(QLabel(f"  {w}"))
        layout.addWidget(wl)
        b = QPushButton("Generate New Word Search")
        b.clicked.connect(self._regen)
        layout.addWidget(b)
        layout.addStretch()

    def _regen(self):
        dlg = NewPuzzleDialog(self)
        dlg.chosen_type = "Word Search"
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pp = dlg.puzzle_params
            np = WordSearchEngine.generate(pp.get("width", 12), pp.get("height", 12),
                                           difficulty=dlg.chosen_difficulty,
                                           category=pp.get("word_category", None))
            self.tab.puzzle = np
            self.tab.undo_stack.clear()
            self.tab.grid_widget.deleteLater()
            self.tab.grid_widget = WordSearchWidget(np, self.tab)
            self.tab.layout().addWidget(self.tab.grid_widget, 1)
            self.tab.editor_panel.deleteLater()
            self.tab.editor_panel = _WordSearchEditor(self.tab)
            self.tab.editor_panel.setFixedWidth(340)
            self.tab.layout().insertWidget(0, self.tab.editor_panel)

# ============================================================================
# THEME ENGINE
# ============================================================================

STYLESHEET_TEMPLATE = """
QMainWindow { background: {bg}; }
QGroupBox {
    font-weight: bold; border: 1px solid {border}; border-radius: 6px;
    margin-top: 10px; padding-top: 14px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {text}; }
QPushButton {
    background: {accent}; color: white; border: none; border-radius: 4px;
    padding: 6px 16px; font-size: 13px;
}
QPushButton:hover { background: #2980b9; }
QPushButton:pressed { background: #1f6da3; }
QPushButton:disabled { background: #7f8c8d; color: #bdc3c7; }
QPushButton#danger { background: #e74c3c; }
QPushButton#danger:hover { background: #c0392b; }
QPushButton#success { background: #27ae60; }
QPushButton#success:hover { background: #1e8449; }
QListWidget {
    border: 1px solid {border}; border-radius: 4px; padding: 4px; background: {surface};
}
QListWidget::item { padding: 5px 8px; border-bottom: 1px solid {border}; }
QListWidget::item:selected { background: {accent}; color: white; }
QTextEdit, QLineEdit, QComboBox, QSpinBox {
    border: 1px solid {border}; border-radius: 4px; padding: 6px;
    background: {surface}; font-size: 13px; color: {text};
}
QTabWidget::pane { border: 1px solid {border}; border-radius: 4px; background: {surface}; }
QTabBar::tab {
    background: {empty_bg}; padding: 8px 20px; margin-right: 2px;
    border-top-left-radius: 4px; border-top-right-radius: 4px; font-size: 13px; color: {text};
}
QTabBar::tab:selected { background: {surface}; border-bottom: 2px solid {accent}; font-weight: bold; }
QToolBar { background: {surface}; border-bottom: 1px solid {border}; padding: 4px; spacing: 6px; }
QStatusBar { background: #2c3e50; color: white; font-size: 12px; }
QScrollArea { background: {bg}; border: none; }
QTableWidget { background: {surface}; color: {text}; gridline-color: {border}; }
QTableWidget::item { padding: 4px; }
QTableWidget::item:selected { background: {accent}; color: white; }
QHeaderView::section { background: #34495e; color: white; padding: 4px; border: 1px solid #2c3e50; }
QRadioButton { color: {text}; spacing: 6px; }
QCheckBox { color: {text}; }
QLabel { color: {text}; }
QProgressBar { border: 1px solid {border}; border-radius: 4px; text-align: center; background: {empty_bg}; color: {text}; }
QProgressBar::chunk { background: {accent}; border-radius: 3px; }
"""

def apply_theme(app, is_dark):
    t = DARK_THEME if is_dark else LIGHT_THEME
    app.setStyleSheet(STYLESHEET_TEMPLATE.format(**t))
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(t["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Base, QColor(t["surface"]))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(t["empty_bg"]))
    pal.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Button, QColor(t["surface"]))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(t["accent"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    app.setPalette(pal)


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self.current_file = None
        self.tabs = []
        self.timer = SolveTimer()
        self.timer.set_callback(self._on_timer_tick)
        self.stats = SolveStatistics()
        self.setWindowTitle("Logic Puzzle Maker Pro")
        self.setMinimumSize(1150, 780)
        self.resize(1250, 850)
        self._build_menu()
        self._build_toolbar()
        self._build_ui()
        self._build_statusbar()
        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_puzzle)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_puzzle)
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_puzzle)
        QShortcut(QKeySequence("Ctrl+W"), self, self._close_tab)
        QShortcut(QKeySequence("Ctrl+H"), self, self._hint_action)
        QShortcut(QKeySequence("Ctrl+I"), self, self._import_text)
        # Progress timer
        self._progress_timer = QTimer()
        self._progress_timer.setInterval(2000)
        self._progress_timer.timeout.connect(self._update_progress)

    @property
    def current_tab(self):
        idx = self.tab_widget.currentIndex()
        if 0 <= idx < len(self.tabs):
            return self.tabs[idx]
        return None

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("&File")
        self._ma(fm, "New Puzzle...", self._new_puzzle, "Ctrl+N")
        fm.addSeparator()
        self._ma(fm, "Open...", self._open_puzzle, "Ctrl+O")
        self._ma(fm, "Save", self._save_puzzle, "Ctrl+S")
        self._ma(fm, "Save As...", self._save_as, "Ctrl+Shift+S")
        fm.addSeparator()
        self._ma(fm, "Import from Text...", self._import_text, "Ctrl+I")
        fm.addSeparator()
        self._ma(fm, "Export as HTML...", self._export_html)
        fm.addSeparator()
        self._ma(fm, "Exit", self.close, "Ctrl+Q")
        em = mb.addMenu("&Edit")
        self._ma(em, "Undo", self._undo, "Ctrl+Z")
        self._ma(em, "Redo", self._redo, "Ctrl+Y")
        em.addSeparator()
        self._ma(em, "Clear Grid", self._clear_grid)
        em.addSeparator()
        self._ma(em, "Set Solution...", self._set_solution)
        pm = mb.addMenu("&Puzzle")
        self._ma(pm, "Check Solution", self._check_solution)
        self._ma(pm, "Get Hint", self._hint_action, "Ctrl+H")
        pm.addSeparator()
        self._ma(pm, "Start Timer", self._start_timer)
        self._ma(pm, "Pause Timer", self._pause_timer)
        self._ma(pm, "Reset Timer", self._reset_timer)
        vm = mb.addMenu("&View")
        self.dark_action = self._ma(vm, "Dark Mode", self._toggle_dark)
        self.dark_action.setCheckable(True)
        vm.addSeparator()
        self._ma(vm, "Close Tab", self._close_tab, "Ctrl+W")
        vm.addSeparator()
        self._ma(vm, "Statistics...", self._show_stats)
        hm = mb.addMenu("&Help")
        self._ma(hm, "How to Use", self._show_help)
        self._ma(hm, "About", self._show_about)

    def _ma(self, menu, text, slot, shortcut=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut) if isinstance(shortcut, str) else shortcut)
        menu.addAction(a)
        return a

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)
        for text, fn, w in [("New", self._new_puzzle, 55), ("Open", self._open_puzzle, 55),
                            ("Save", self._save_puzzle, 55)]:
            b = QPushButton(text)
            b.setFixedWidth(w)
            b.clicked.connect(fn)
            tb.addWidget(b)
        tb.addSeparator()
        for text, fn, w in [("Undo", self._undo, 55), ("Redo", self._redo, 55),
                            ("Hint", self._hint_action, 55)]:
            b = QPushButton(text)
            b.setFixedWidth(w)
            b.clicked.connect(fn)
            tb.addWidget(b)
        tb.addSeparator()
        b = QPushButton("Check")
        b.setFixedWidth(55)
        b.clicked.connect(self._check_solution)
        tb.addWidget(b)
        b = QPushButton("Clear")
        b.setFixedWidth(55)
        b.clicked.connect(self._clear_grid)
        tb.addWidget(b)
        tb.addSeparator()
        self.timer_label = QLabel("  00:00")
        self.timer_label.setStyleSheet("font-size:14px; font-weight:bold; color:#2c3e50; padding:0 8px;")
        tb.addWidget(self.timer_label)
        for text, fn in [("Start", self._start_timer), ("Pause", self._pause_timer), ("Reset", self._reset_timer)]:
            b = QPushButton(text)
            b.setFixedWidth(50)
            b.clicked.connect(fn)
            tb.addWidget(b)
        tb.addSeparator()
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(120)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        tb.addWidget(self.progress_bar)
        tb.addSeparator()
        b = QPushButton("Dark")
        b.setCheckable(True)
        b.setFixedWidth(55)
        b.toggled.connect(self._toggle_dark)
        tb.addWidget(b)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab_at)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_widget)
        self._show_welcome()

    def _build_statusbar(self):
        self.statusBar().showMessage("Ready - click New to create a puzzle.")

    def _show_welcome(self):
        if self.tabs:
            return
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setAlignment(Qt.AlignCenter)
        title = QLabel("Logic Puzzle Maker Pro")
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color:#2c3e50; margin-bottom:8px;")
        wl.addWidget(title)
        subtitle = QLabel("Create, solve, and export 6 types of logic puzzles")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color:#7f8c8d; margin-bottom:30px;")
        wl.addWidget(subtitle)
        tg = QGridLayout()
        tg.setSpacing(16)
        cards = [
            ("Logic Grid", "Category-based deduction\npuzzles with clues", self._qn_logic_grid),
            ("Nonogram", "Picture logic with\nrow/column clues", self._qn_nonogram),
            ("Word Logic", "Einstein riddle\nconstraint puzzles", self._qn_word_logic),
            ("Kakuro", "Cross-sum number\nplacement puzzle", self._qn_kakuro),
            ("Word Search", "Find hidden words\nin a letter grid", self._qn_word_search),
        ]
        icons = ["\U0001f4ca", "\U0001f7e9", "\U0001f9e0", "\U0001f522", "\U0001f50d"]
        for i, (name, desc, fn) in enumerate(cards):
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background:white; border:1px solid #dcdde1; border-radius:8px; padding:16px;}"
                "QFrame:hover{border-color:#3498db;}")
            card.setFixedSize(200, 140)
            card.setCursor(Qt.PointingHandCursor)
            cl = QVBoxLayout(card)
            il = QLabel(icons[i])
            il.setFont(QFont("Segoe UI", 32))
            il.setAlignment(Qt.AlignCenter)
            cl.addWidget(il)
            n = QLabel(name)
            n.setFont(QFont("Segoe UI", 13, QFont.Bold))
            n.setAlignment(Qt.AlignCenter)
            cl.addWidget(n)
            d = QLabel(desc)
            d.setAlignment(Qt.AlignCenter)
            d.setStyleSheet("color:#7f8c8d; font-size:11px;")
            cl.addWidget(d)
            card.mousePressEvent = lambda e, f=fn: f()
            tg.addWidget(card, i // 3, i % 3)
        wl.addLayout(tg)
        self.tab_widget.addTab(w, "Welcome")
        self.tab_widget.setTabsClosable(False)

    def _qn_logic_grid(self): self._create_puzzle("Logic Grid", "Medium", True, {"size": 4})
    def _qn_nonogram(self): self._create_puzzle("Nonogram", "Medium", True, {"width": 10, "height": 10})
    def _qn_word_logic(self): self._create_puzzle("Word Logic", "Medium", True, {})
    def _qn_kakuro(self): self._create_puzzle("Kakuro", "Medium", True, {"width": 8, "height": 8})
    def _qn_word_search(self): self._create_puzzle("Word Search", "Medium", True, {"width": 12, "height": 12})

    def _new_puzzle(self):
        dlg = NewPuzzleDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._create_puzzle(dlg.chosen_type, dlg.chosen_difficulty, dlg.auto_generate, dlg.puzzle_params)

    def _create_puzzle(self, ptype, difficulty, auto_gen, params):
        if auto_gen:
            if ptype == "Nonogram":
                puzzle = NonogramEngine.generate(params.get("width", 10), params.get("height", 10), difficulty=difficulty)
            elif ptype == "Logic Grid":
                puzzle = LogicGridGenerator.generate(params.get("size", 4), difficulty)
            elif ptype == "Word Logic":
                puzzle = WordLogicGenerator.generate(difficulty=difficulty)
            elif ptype == "Kakuro":
                puzzle = KakuroEngine.generate(params.get("width", 8), params.get("height", 8), difficulty=difficulty)
            elif ptype == "Word Search":
                puzzle = WordSearchEngine.generate(params.get("width", 12), params.get("height", 12),
                                                   difficulty=difficulty, category=params.get("word_category", None))
            else:
                puzzle = LogicGridPuzzle()
        else:
            if ptype == "Nonogram": puzzle = NonogramPuzzle()
            elif ptype == "Word Logic": puzzle = WordLogicPuzzle()
            elif ptype == "Kakuro": puzzle = KakuroPuzzle()
            elif ptype == "Word Search": puzzle = WordSearchPuzzle()
            else: puzzle = LogicGridPuzzle()
            puzzle.difficulty = difficulty
        self._add_tab(puzzle)
        self.statusBar().showMessage(f"Created {ptype} puzzle ({difficulty}).")

    def _add_tab(self, puzzle):
        if len(self.tabs) == 0 and self.tab_widget.count() == 1:
            self.tab_widget.removeTab(0)
            self.tab_widget.setTabsClosable(True)
        tab = PuzzleTab(puzzle)
        self.tabs.append(tab)
        label = f"{puzzle.type_name}: {puzzle.title[:20]}"
        self.tab_widget.addTab(tab, label)
        self.tab_widget.setCurrentIndex(len(self.tabs) - 1)
        self._progress_timer.start()

    def _close_tab(self):
        if self.current_tab:
            self._close_tab_at(self.tab_widget.currentIndex())

    def _close_tab_at(self, idx):
        if 0 <= idx < len(self.tabs):
            self.tabs.pop(idx)
            self.tab_widget.removeTab(idx)
            if not self.tabs:
                self.tab_widget.setTabsClosable(False)
                self._show_welcome()
                self._progress_timer.stop()
                self.progress_bar.setValue(0)

    def _on_tab_changed(self, idx):
        tab = self.current_tab
        if tab:
            self.statusBar().showMessage(
                f"[{tab.puzzle.type_name}] {tab.puzzle.title}  |  "
                f"Difficulty: {tab.puzzle.difficulty}  |  "
                f"Score: {DifficultyScorer.score(tab.puzzle)}/100  |  "
                f"Undo: {'yes' if tab.undo_stack.can_undo() else 'no'}  "
                f"Redo: {'yes' if tab.undo_stack.can_redo() else 'no'}")

    def _undo(self):
        tab = self.current_tab
        if tab:
            tab.undo()
            self.statusBar().showMessage("Undo.")

    def _redo(self):
        tab = self.current_tab
        if tab:
            tab.redo()
            self.statusBar().showMessage("Redo.")

    def _start_timer(self): self.timer.start()
    def _pause_timer(self): self.timer.pause()
    def _reset_timer(self):
        self.timer.reset()
        self.timer_label.setText("  00:00")
        self.statusBar().showMessage("Timer reset.")

    def _on_timer_tick(self, text):
        self.timer_label.setText(f"  {text}")

    def _update_progress(self):
        tab = self.current_tab
        if tab:
            p = tab.get_progress()
            self.progress_bar.setValue(int(p * 100))

    def _check_solution(self):
        tab = self.current_tab
        if not tab:
            return
        ok, msg = tab.check()
        if ok:
            self.timer.pause()
            elapsed = self.timer.elapsed_seconds()
            self.stats.record_solve(tab.puzzle.type_name, tab.puzzle.title,
                                    tab.puzzle.difficulty, elapsed, tab.hints_used, True)
            QMessageBox.information(self, "Correct!", f"{msg}\n\nTime: {elapsed // 60:02d}:{elapsed % 60:02d}  Hints: {tab.hints_used}")
        else:
            QMessageBox.information(self, "Not Yet", msg)

    def _hint_action(self):
        tab = self.current_tab
        if tab:
            tab.save_undo_state()
            result = tab.give_hint()
            if result:
                self.statusBar().showMessage("Hint revealed!")
            else:
                self.statusBar().showMessage("No hint available.")

    def _clear_grid(self):
        tab = self.current_tab
        if tab:
            tab.save_undo_state()
            tab.clear_grid()

    def _set_solution(self):
        tab = self.current_tab
        if not tab:
            return
        p = tab.puzzle
        if isinstance(p, LogicGridPuzzle):
            if not p.is_valid():
                QMessageBox.warning(self, "Invalid", "Need 2+ categories with equal items.")
                return
            dlg = SolutionDialog(p, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                p.solution = dlg.solution
                self.statusBar().showMessage("Solution set.")
        else:
            QMessageBox.information(self, "Info", "Solution is set automatically for generated puzzles.")

    def _open_puzzle(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Puzzle", "",
            "Puzzle Files (*.lpuzzle *.json);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            puzzle = puzzle_from_dict(data)
            self.current_file = Path(path)
            self._add_tab(puzzle)
            self.statusBar().showMessage(f"Opened: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open:\n{e}")

    def _save_puzzle(self):
        tab = self.current_tab
        if not tab:
            return
        if self.current_file:
            self._save_to(self.current_file, tab.puzzle)
        else:
            self._save_as()

    def _save_as(self):
        tab = self.current_tab
        if not tab:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Puzzle", tab.puzzle.title or "puzzle",
            "Puzzle Files (*.lpuzzle);;JSON (*.json);;All Files (*)")
        if path:
            self.current_file = Path(path)
            self._save_to(Path(path), tab.puzzle)

    def _save_to(self, path, puzzle):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(puzzle.to_dict(), f, indent=2, ensure_ascii=False)
            self.statusBar().showMessage(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed:\n{e}")

    def _import_text(self):
        dlg = ImportTextDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.imported_puzzle:
            self._add_tab(dlg.imported_puzzle)
            self.statusBar().showMessage("Puzzle imported from text.")

    def _export_html(self):
        tab = self.current_tab
        if not tab:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export HTML", tab.puzzle.title or "puzzle",
            "HTML Files (*.html);;All Files (*)")
        if not path:
            return
        html = _generate_html(tab.puzzle)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self.statusBar().showMessage(f"Exported: {path}")
            QMessageBox.information(self, "Exported",
                f"Saved to:\n{path}\n\nOpen in browser, then Ctrl+P to print/save as PDF.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")

    def _toggle_dark(self, checked=None):
        self.dark_mode = not self.dark_mode
        apply_theme(QApplication.instance(), self.dark_mode)
        self.dark_action.setChecked(self.dark_mode)

    def _show_stats(self):
        dlg = StatisticsDialog(self.stats, self)
        dlg.exec()

    def _show_help(self):
        QMessageBox.information(self, "How to Use", """
<h2>Logic Puzzle Maker Pro - Guide</h2>
<h3>Puzzle Types</h3>
<ul>
  <li><b>Logic Grid</b> - Category deduction. Add categories, write clues, mark the grid.
    Right-click cells for pencil notes. Auto-solve and auto-generate clues available.</li>
  <li><b>Nonogram</b> - Fill cells to match row/column number clues.
    Left-click = fill, right-click = mark X.</li>
  <li><b>Word Logic</b> - Einstein riddles. Read constraints and pick correct values.</li>
  <li><b>Kakuro</b> - Fill numbers 1-9 so each row/column run sums to the clue.
    Digits in a run must be unique.</li>
  <li><b>Word Search</b> - Click start then end of a word to select it.
    Words can go in any direction (horizontal, vertical, diagonal).</li>
</ul>
<h3>Features</h3>
<ul>
  <li><b>Undo/Redo</b> - Ctrl+Z / Ctrl+Y</li>
  <li><b>Timer</b> - Track solve time</li>
  <li><b>Hints</b> - Reveal one correct cell (Ctrl+H)</li>
  <li><b>Check</b> - Verify solution, auto-record stats</li>
  <li><b>Import</b> - Paste text to import (Ctrl+I)</li>
  <li><b>Statistics</b> - View solve history</li>
  <li><b>Dark Mode</b> - Toggle in toolbar</li>
  <li><b>Save/Load</b> - .lpuzzle JSON files</li>
  <li><b>Export HTML</b> - Print-ready sheets</li>
</ul>""")

    def _show_about(self):
        QMessageBox.about(self, "About", """
<h2>Logic Puzzle Maker Pro</h2>
<p>Version 3.0</p>
<p>Create, solve, and export 5 types of logic puzzles with
auto-generation, solving, difficulty scoring, and statistics.</p>
<p><b>Puzzle Types:</b> Logic Grid, Nonogram, Word Logic, Kakuro, Word Search</p>
<p>Built with <b>PySide6</b>.</p>""")


# ============================================================================
# HTML GENERATOR
# ============================================================================

def _generate_html(puzzle):
    t = puzzle.type_name
    clues_html = "".join(f"<li>{c}</li>" for c in puzzle.clues)

    if t == "Logic Grid" and isinstance(puzzle, LogicGridPuzzle):
        cats = puzzle.categories
        grids_html = ""
        for ci in range(1, len(cats)):
            a, b = cats[0], cats[ci]
            hdr = "".join(f"<th>{x}</th>" for x in b.items)
            rows = ""
            for i, item in enumerate(a.items):
                cells = "".join('<td class="empty">&nbsp;&nbsp;</td>' for _ in b.items)
                rows += f"<tr><th>{item}</th>{cells}</tr>"
            grids_html += f"<h3>{a.name} x {b.name}</h3><table><thead><tr><th></th>{hdr}</tr></thead><tbody>{rows}</tbody></table>"
        body = f"<h1>{puzzle.title}</h1><div class='clues'><h2>Clues</h2><ol>{clues_html}</ol></div><h2>Solve</h2><p>Mark cells X (no) or O (yes).</p>{grids_html}"
    elif t == "Kakuro" and isinstance(puzzle, KakuroPuzzle):
        rows = ""
        for r in range(puzzle.rows):
            cells = ""
            for c in range(puzzle.cols):
                ct = puzzle.layout[r][c] if r < len(puzzle.layout) and c < len(puzzle.layout[0]) else 0
                if ct == 0:
                    cells += "<td class='black'>&nbsp;</td>"
                elif ct == 1:
                    rs = puzzle.row_sums.get((r, c), "")
                    cs = puzzle.col_sums.get((r, c), "")
                    cells += f"<td class='clue'><span class='rs'>{rs}</span><span class='cs'>{cs}</span></td>"
                else:
                    cells += "<td class='empty'>&nbsp;</td>"
            rows += f"<tr>{cells}</tr>"
        body = f"<h1>{puzzle.title}</h1><p>Fill digits 1-9. Each run must sum to its clue with no repeats.</p><table class='kakuro'>{rows}</table>"
    elif t == "Word Search" and isinstance(puzzle, WordSearchPuzzle):
        wl = "".join(f"<li>{w}</li>" for w in puzzle.words)
        rows = ""
        for r in range(puzzle.height):
            cells = "".join(f"<td>{puzzle.grid[r][c]}</td>" for c in range(puzzle.width)
                           if r < len(puzzle.grid) and c < len(puzzle.grid[0]))
            rows += f"<tr>{cells}</tr>"
        body = f"<h1>{puzzle.title}</h1><div class='clues'><h2>Words</h2><ul>{wl}</ul></div><table class='ws'>{rows}</table>"
    elif t == "Nonogram" and isinstance(puzzle, NonogramPuzzle):
        body = f"<h1>{puzzle.title}</h1><div class='clues'><h2>Row Clues</h2><ol>{''.join(f'<li>{c}</li>' for c in puzzle.row_clues)}</ol></div>"
        body += f"<div class='clues'><h2>Column Clues</h2><ol>{''.join(f'<li>{c}</li>' for c in puzzle.col_clues)}</ol></div>"
    elif t == "Word Logic" and isinstance(puzzle, WordLogicPuzzle):
        vh = ""
        for v in puzzle.variables:
            vh += f"<tr><th>{v['name']}</th><td>{', '.join(v['domain'])}</td></tr>"
        body = f"<h1>{puzzle.title}</h1><table>{vh}</table><div class='clues'><h2>Clues</h2><ol>{clues_html}</ol></div>"
    else:
        body = f"<h1>{puzzle.title}</h1><p>Clues:</p><ol>{clues_html}</ol>"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{puzzle.title}</title>
<style>
body {{ font-family:'Segoe UI',Arial,sans-serif; max-width:900px; margin:40px auto; padding:0 20px; color:#2c3e50; }}
h1 {{ text-align:center; border-bottom:2px solid #3498db; padding-bottom:10px; }}
.clues {{ background:#f8f9fa; padding:16px 24px; border-radius:8px; margin:20px 0; }}
.clues ol {{ margin:0; padding-left:20px; }} .clues li {{ margin:4px 0; line-height:1.5; }}
table {{ border-collapse:collapse; width:100%; margin:12px 0; }}
th,td {{ border:1px solid #bdc3c7; padding:8px; text-align:center; }}
th {{ background:#34495e; color:white; }}
td.empty {{ background:#ecf0f1; height:32px; }}
td.black {{ background:#34495e; }}
td.clue {{ background:#dfe6e9; position:relative; height:32px; }}
td.clue .rs {{ position:absolute; top:1px; left:3px; font-size:10px; font-weight:bold; }}
td.clue .cs {{ position:absolute; bottom:1px; right:3px; font-size:10px; font-weight:bold; }}
table.kakuro {{ max-width:500px; margin:20px auto; }}
table.kakuro td {{ width:36px; height:36px; }}
table.ws {{ max-width:500px; margin:20px auto; }}
table.ws td {{ width:28px; height:28px; font-size:14px; font-weight:bold; font-family:monospace; }}
@media print {{ body {{ margin:20px; }} }}
</style></head><body>{body}</body></html>"""


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_theme(app, is_dark=False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
