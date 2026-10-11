"""
Logic Puzzle App — A collection of brain-training logic puzzles built with Kivy.
Puzzles: Nonogram, Lights Out, Mastermind, Logic Grid
"""

import random
import copy
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton
from kivy.properties import NumericProperty, BooleanProperty, ListProperty
from kivy.core.window import Window
from kivy.metrics import dp, sp


# ═══════════════════════════════════════════════════════════════════
#  NONOGRAM (PICROSS)
# ═══════════════════════════════════════════════════════════════════

class NonogramCell(Button):
    cell_state = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.bind(cell_state=self._refresh)

    def _refresh(self, *_):
        s = self.cell_state
        if s == 0:
            self.text = ''
            self.background_color = (0.96, 0.96, 0.98, 1)
            self.color = (0, 0, 0, 1)
        elif s == 1:
            self.text = ''
            self.background_color = (0.15, 0.15, 0.25, 1)
        else:
            self.text = '✕'
            self.background_color = (0.88, 0.88, 0.90, 1)
            self.color = (0.72, 0.15, 0.15, 1)


class NonogramScreen(Screen):
    def __init__(self, grid_size=5, **kwargs):
        super().__init__(**kwargs)
        self.gs = grid_size
        self.solution = []
        self.player_grid = []
        self.row_clues = []
        self.col_clues = []
        self.cells = {}
        self.fill_mode = True
        self._build_ui()
        self.new_puzzle()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        hdr = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = Button(text='← Back', background_color=(0.30, 0.30, 0.55, 1))
        back.bind(on_press=lambda _: setattr(self.manager, 'current', 'menu'))
        title = Label(text=f'Nonogram {self.gs}×{self.gs}',
                      font_size=sp(20), color=(0.15, 0.15, 0.45, 1))
        new_btn = Button(text='New', background_color=(0.20, 0.55, 0.20, 1))
        new_btn.bind(on_press=lambda _: self.new_puzzle())
        for w in (back, title, new_btn):
            hdr.add_widget(w)
        root.add_widget(hdr)

        mode_bar = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        self.fill_btn = ToggleButton(text='Fill ■', group='nono_mode', state='down',
                                     background_color=(0.20, 0.50, 0.80, 1))
        self.mark_btn = ToggleButton(text='Mark ✕', group='nono_mode',
                                     background_color=(0.70, 0.30, 0.30, 1))
        self.fill_btn.bind(on_press=lambda _: setattr(self, 'fill_mode', True))
        self.mark_btn.bind(on_press=lambda _: setattr(self, 'fill_mode', False))
        mode_bar.add_widget(self.fill_btn)
        mode_bar.add_widget(self.mark_btn)
        root.add_widget(mode_bar)

        self.scroll = ScrollView(do_scroll_x=True, do_scroll_y=True)
        self.scroll_content = BoxLayout(size_hint=(None, None), orientation='vertical')
        self.scroll.add_widget(self.scroll_content)
        root.add_widget(self.scroll)

        chk = Button(text='Check Solution', size_hint_y=None, height=dp(48),
                     background_color=(0.20, 0.45, 0.75, 1), font_size=sp(17))
        chk.bind(on_press=self._check)
        root.add_widget(chk)

        self.add_widget(root)

    def new_puzzle(self):
        gs = self.gs
        self.solution = [[random.choice([0, 1]) for _ in range(gs)] for _ in range(gs)]
        total = sum(sum(r) for r in self.solution)
        if total < gs or total > gs * (gs - 1):
            self.new_puzzle()
            return
        self.row_clues = self._clues(self.solution)
        self.col_clues = self._clues(
            [[self.solution[r][c] for r in range(gs)] for c in range(gs)])
        self.player_grid = [[0] * gs for _ in range(gs)]
        self.cells = {}
        self._build_grid()

    @staticmethod
    def _clues(lines):
        result = []
        for line in lines:
            runs, n = [], 0
            for v in line:
                if v: n += 1
                elif n: runs.append(n); n = 0
            if n: runs.append(n)
            result.append(runs or [0])
        return result

    def _build_grid(self):
        self.scroll_content.clear_widgets()
        gs = self.gs
        max_rc = max(len(c) for c in self.row_clues)
        max_cc = max(len(c) for c in self.col_clues)
        cols = max_rc + gs
        rows = max_cc + gs
        cs = min(dp(38), max(dp(22), (Window.width - dp(30)) // cols))

        grid = GridLayout(cols=cols, rows=rows, size_hint=(None, None), spacing=dp(1))
        grid.size = (cols * (cs + 1), rows * (cs + 1))
        self.scroll_content.size = grid.size

        for row in range(rows):
            for col in range(cols):
                if row < max_cc and col < max_rc:
                    w = Label(size_hint=(None, None), size=(cs, cs))
                elif row < max_cc:
                    cidx = col - max_rc
                    clue = self.col_clues[cidx]
                    off = max_cc - len(clue)
                    t = str(clue[row - off]) if row >= off else ''
                    w = Label(text=t, size_hint=(None, None), size=(cs, cs),
                              font_size=sp(13), color=(0.20, 0.20, 0.50, 1))
                elif col < max_rc:
                    ridx = row - max_cc
                    clue = self.row_clues[ridx]
                    off = max_rc - len(clue)
                    t = str(clue[col - off]) if col >= off else ''
                    w = Label(text=t, size_hint=(None, None), size=(cs, cs),
                              font_size=sp(13), color=(0.20, 0.20, 0.50, 1))
                else:
                    r, c = row - max_cc, col - max_rc
                    cell = NonogramCell(size=(cs, cs))
                    cell.bind(on_press=lambda _, r=r, c=c: self._tap(r, c))
                    self.cells[(r, c)] = cell
                    w = cell
                grid.add_widget(w)
        self.scroll_content.add_widget(grid)

    def _tap(self, r, c):
        cell = self.cells[(r, c)]
        if self.fill_mode:
            if cell.cell_state == 1:
                cell.cell_state = 0; self.player_grid[r][c] = 0
            else:
                cell.cell_state = 1; self.player_grid[r][c] = 1
        else:
            if cell.cell_state == 2: cell.cell_state = 0
            else: cell.cell_state = 2; self.player_grid[r][c] = 0

    def _check(self, _=None):
        gs = self.gs
        p_rows = [[1 if self.player_grid[r][c] else 0 for c in range(gs)] for r in range(gs)]
        p_cols = [[1 if self.player_grid[r][c] else 0 for r in range(gs)] for c in range(gs)]
        if self._clues(p_rows) == self.row_clues and self._clues(p_cols) == self.col_clues:
            self._popup('🎉 Solved!', 'You solved the Nonogram!')
        else:
            self._popup('Not Quite', 'Some cells are wrong — keep trying!')

    def _popup(self, title, msg):
        Popup(title=title, content=Label(text=msg), size_hint=(0.7, 0.35)).open()


# ═══════════════════════════════════════════════════════════════════
#  LIGHTS OUT
# ═══════════════════════════════════════════════════════════════════

class LightCell(Button):
    is_on = BooleanProperty(False)

    def __init__(self, r=0, c=0, **kw):
        super().__init__(**kw)
        self.r, self.c = r, c
        self.font_size = sp(20)
        self.bind(is_on=self._paint)

    def _paint(self, *_):
        if self.is_on:
            self.background_color = (1.0, 0.82, 0.10, 1)
            self.text = '💡'
        else:
            self.background_color = (0.22, 0.22, 0.28, 1)
            self.text = ''


class LightsOutScreen(Screen):
    def __init__(self, grid_size=5, **kwargs):
        super().__init__(**kwargs)
        self.gs = grid_size
        self.state = []
        self.cells = {}
        self.moves = 0
        self._build_ui()
        self.new_puzzle()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        hdr = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = Button(text='← Back', background_color=(0.30, 0.30, 0.55, 1))
        back.bind(on_press=lambda _: setattr(self.manager, 'current', 'menu'))
        title = Label(text=f'Lights Out {self.gs}×{self.gs}',
                      font_size=sp(20), color=(0.15, 0.15, 0.45, 1))
        new_btn = Button(text='New', background_color=(0.20, 0.55, 0.20, 1))
        new_btn.bind(on_press=lambda _: self.new_puzzle())
        for w in (back, title, new_btn):
            hdr.add_widget(w)
        root.add_widget(hdr)

        self.moves_lbl = Label(text='Moves: 0', size_hint_y=None, height=dp(30),
                               font_size=sp(15), color=(0.40, 0.40, 0.40, 1))
        root.add_widget(self.moves_lbl)

        self.grid_area = BoxLayout()
        root.add_widget(self.grid_area)

        info = Label(text='Tap a light to toggle it and its neighbours.\nGoal: turn all lights OFF.',
                     size_hint_y=None, height=dp(50), font_size=sp(13), color=(0.45, 0.45, 0.45, 1))
        root.add_widget(info)
        self.add_widget(root)

    def new_puzzle(self):
        gs = self.gs
        self.state = [[False] * gs for _ in range(gs)]
        for _ in range(random.randint(gs, gs * 3)):
            self._toggle(random.randint(0, gs - 1), random.randint(0, gs - 1), update_ui=False)
        if not any(any(r) for r in self.state):
            self.new_puzzle()
            return
        self.moves = 0
        self.moves_lbl.text = 'Moves: 0'
        self.cells = {}
        self._build_grid()

    def _toggle(self, r, c, update_ui=True):
        for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.gs and 0 <= nc < self.gs:
                self.state[nr][nc] = not self.state[nr][nc]
                if update_ui and (nr, nc) in self.cells:
                    self.cells[(nr, nc)].is_on = self.state[nr][nc]

    def _build_grid(self):
        self.grid_area.clear_widgets()
        self.cells = {}
        grid = GridLayout(cols=self.gs, rows=self.gs, spacing=dp(3))
        for r in range(self.gs):
            for c in range(self.gs):
                cell = LightCell(r, c)
                cell.is_on = self.state[r][c]
                cell.bind(on_press=self._press)
                self.cells[(r, c)] = cell
                grid.add_widget(cell)
        self.grid_area.add_widget(grid)

    def _press(self, inst):
        self._toggle(inst.r, inst.c)
        self.moves += 1
        self.moves_lbl.text = f'Moves: {self.moves}'
        if not any(any(r) for r in self.state):
            Popup(title='🎉 Solved!',
                  content=Label(text=f'All lights off in {self.moves} moves!'),
                  size_hint=(0.75, 0.35)).open()


# ═══════════════════════════════════════════════════════════════════
#  MASTERMIND (CODE BREAKING)
# ═══════════════════════════════════════════════════════════════════

class MastermindScreen(Screen):
    """Guess the secret 4-color code. Feedback: ● = right color & place, ○ = right color wrong place."""
    COLORS = [
        ('Red',    (0.90, 0.20, 0.20, 1)),
        ('Green',  (0.20, 0.75, 0.20, 1)),
        ('Blue',   (0.20, 0.40, 0.90, 1)),
        ('Yellow', (0.90, 0.90, 0.20, 1)),
        ('Purple', (0.65, 0.20, 0.80, 1)),
        ('Orange', (0.90, 0.50, 0.15, 1)),
    ]
    CODE_LEN = 4
    MAX_GUESSES = 10

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.secret = []
        self.guesses = []  # list of tuples (guess_list, blacks, whites)
        self.current_guess = [None] * self.CODE_LEN
        self.selected_color_idx = 0
        self._build_ui()
        self.new_puzzle()

    def _build_ui(self):
        self.root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = Button(text='← Back', background_color=(0.30, 0.30, 0.55, 1))
        back.bind(on_press=lambda _: setattr(self.manager, 'current', 'menu'))
        title = Label(text='Mastermind', font_size=sp(20), color=(0.15, 0.15, 0.45, 1))
        new_btn = Button(text='New', background_color=(0.20, 0.55, 0.20, 1))
        new_btn.bind(on_press=lambda _: self.new_puzzle())
        for w in (back, title, new_btn):
            hdr.add_widget(w)
        self.root.add_widget(hdr)

        # History Scroll
        self.scroll = ScrollView()
        self.history_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(5))
        self.scroll.add_widget(self.history_layout)
        self.root.add_widget(self.scroll)

        # Current Guess & Controls
        bottom = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(160), spacing=dp(4))
        
        # Guess slots
        guess_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(5))
        self.slots = []
        for i in range(self.CODE_LEN):
            btn = Button(background_color=(0.5, 0.5, 0.5, 1), size_hint_x=1)
            btn.bind(on_press=lambda _, idx=i: self._slot_tap(idx))
            self.slots.append(btn)
            guess_row.add_widget(btn)
        bottom.add_widget(guess_row)

        # Palette
        pal_row = GridLayout(cols=len(self.COLORS), size_hint_y=None, height=dp(45), spacing=dp(3))
        self.pal_btns = []
        for idx, (name, color) in enumerate(self.COLORS):
            btn = ToggleButton(text=name[:1], background_color=color, group='mm_pal',
                               font_size=sp(14), color=(1, 1, 1, 1))
            if idx == 0:
                btn.state = 'down'
            btn.bind(on_press=lambda _, i=i: setattr(self, 'selected_color_idx', i))
            self.pal_btns.append(btn)
            pal_row.add_widget(btn)
        bottom.add_widget(pal_row)

        # Check Button
        chk_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
        chk = Button(text='Check Guess', background_color=(0.20, 0.45, 0.75, 1), font_size=sp(17))
        chk.bind(on_press=self._check_guess)
        clear_btn = Button(text='Clear', background_color=(0.55, 0.25, 0.25, 1), font_size=sp(15))
        clear_btn.bind(on_press=self._clear_guess)
        chk_row.add_widget(chk)
        chk_row.add_widget(clear_btn)
        bottom.add_widget(chk_row)

        self.root.add_widget(bottom)
        self.add_widget(self.root)

    def new_puzzle(self):
        self.secret = [random.randint(0, len(self.COLORS) - 1) for _ in range(self.CODE_LEN)]
        self.guesses = []
        self.current_guess = [None] * self.CODE_LEN
        self._refresh_slots()
        self.history_layout.clear_widgets()
        self.history_layout.height = dp(10)
        # Add legend
        leg = Label(text='● = Right color & position   ○ = Right color, wrong position',
                    size_hint_y=None, height=dp(30), font_size=sp(12), color=(0.4, 0.4, 0.4, 1))
        self.history_layout.add_widget(leg)

    def _slot_tap(self, idx):
        self.current_guess[idx] = self.selected_color_idx
        self._refresh_slots()

    def _refresh_slots(self):
        for i, slot in enumerate(self.slots):
            c = self.current_guess[i]
            if c is not None:
                slot.background_color = self.COLORS[c][1]
                slot.text = ''
            else:
                slot.background_color = (0.5, 0.5, 0.5, 1)
                slot.text = '?'
                slot.color = (1, 1, 1, 1)

    def _clear_guess(self, _=None):
        self.current_guess = [None] * self.CODE_LEN
        self._refresh_slots()

    def _check_guess(self, _=None):
        if None in self.current_guess:
            Popup(title='Incomplete', content=Label(text='Fill all 4 slots first!'),
                  size_hint=(0.7, 0.3)).open()
            return

        guess = list(self.current_guess)
        blacks, whites = self._evaluate(guess)
        self.guesses.append((guess, blacks, whites))
        
        self._add_history_row(guess, blacks, whites)
        
        if blacks == self.CODE_LEN:
            self._reveal_and_win()
        elif len(self.guesses) >= self.MAX_GUESSES:
            self._reveal_and_lose()
        else:
            self._clear_guess()

    def _evaluate(self, guess):
        secret = list(self.secret)
        blacks = 0
        # First pass: exact matches
        for i in range(self.CODE_LEN):
            if guess[i] == secret[i]:
                blacks += 1
                secret[i] = -1
                guess[i] = -2
        # Second pass: color matches
        whites = 0
        for i in range(self.CODE_LEN):
            if guess[i] == -2:
                continue
            if guess[i] in secret:
                whites += 1
                secret[secret.index(guess[i])] = -1
        return blacks, whites

    def _add_history_row(self, guess, blacks, whites):
        row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(4))
        
        # Guess display
        g_box = BoxLayout(spacing=dp(2))
        for c_idx in guess:
            b = Button(background_color=self.COLORS[c_idx][1], disabled=True)
            g_box.add_widget(b)
        row.add_widget(g_box)
        
        # Feedback display
        fb = '●' * blacks + '○' * whites
        fb_lbl = Label(text=fb, font_size=sp(22), color=(0, 0, 0, 1),
                       size_hint_x=0.5)
        row.add_widget(fb_lbl)
        
        self.history_layout.add_widget(row)
        self.history_layout.height += dp(50)

    def _reveal_and_win(self):
        self._show_secret()
        Popup(title='🎉 Cracked!', content=Label(text='You broke the code!'),
              size_hint=(0.7, 0.35)).open()

    def _reveal_and_lose(self):
        self._show_secret()
        Popup(title='Out of Turns!', content=Label(text='Better luck next time!'),
              size_hint=(0.7, 0.35)).open()

    def _show_secret(self):
        # Disable check button by revealing code at top
        secret_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(2))
        for c_idx in self.secret:
            b = Button(background_color=self.COLORS[c_idx][1], disabled=True)
            secret_box.add_widget(b)
        self.history_layout.add_widget(secret_box)
        self.history_layout.height += dp(50)


# ═══════════════════════════════════════════════════════════════════
#  LOGIC GRID (ELIMINATION PUZZLE)
# ═══════════════════════════════════════════════════════════════════

class LogicGridScreen(Screen):
    PUZZLE_TEMPLATES = [
        {'categories': ['Person', 'Pet', 'Colour'],
         'items': {'Person': ['Alice', 'Bob', 'Carol'],
                   'Pet':     ['Cat', 'Dog', 'Fish'],
                   'Colour':  ['Red', 'Blue', 'Green']}},
        {'categories': ['Person', 'Drink', 'Food'],
         'items': {'Person': ['Dan', 'Eve', 'Frank'],
                   'Drink':  ['Tea', 'Coffee', 'Milk'],
                   'Food':   ['Pizza', 'Burger', 'Salad']}},
        {'categories': ['Person', 'Sport', 'Subject'],
         'items': {'Person': ['Grace', 'Henry', 'Ivy'],
                   'Sport':  ['Tennis', 'Soccer', 'Golf'],
                   'Subject':['Math', 'Art', 'Music']}},
        {'categories': ['Kid', 'Toy', 'Season'],
         'items': {'Kid':    ['Liam', 'Mia', 'Noah'],
                   'Toy':    ['Robot', 'Doll', 'Puzzle'],
                   'Season': ['Spring', 'Summer', 'Winter']}},
        {'categories': ['Friend', 'Hobby', 'Country'],
         'items': {'Friend': ['Olga', 'Paul', 'Quinn'],
                   'Hobby':  ['Reading', 'Cooking', 'Hiking'],
                   'Country':['France', 'Japan', 'Brazil']}},
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.solution = {}
        self.clues = []
        self.categories = []
        self.items = {}
        self.sel = {}
        self.btns = {}
        self._sel_popup = None
        self._build_ui()
        self.new_puzzle()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        hdr = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = Button(text='← Back', background_color=(0.30, 0.30, 0.55, 1))
        back.bind(on_press=lambda _: setattr(self.manager, 'current', 'menu'))
        title = Label(text='Logic Grid', font_size=sp(20), color=(0.15, 0.15, 0.45, 1))
        new_btn = Button(text='New', background_color=(0.20, 0.55, 0.20, 1))
        new_btn.bind(on_press=lambda _: self.new_puzzle())
        for w in (back, title, new_btn):
            hdr.add_widget(w)
        root.add_widget(hdr)

        scroll = ScrollView(size_hint_y=0.30)
        self.clues_lbl = Label(text='', font_size=sp(14), color=(0.25, 0.25, 0.35, 1),
                               halign='left', valign='top', size_hint_y=None, padding=(dp(12), dp(8)))
        self.clues_lbl.bind(width=lambda *a: setattr(self.clues_lbl, 'text_size', (self.clues_lbl.width - dp(24), None)),
                            texture_size=lambda *a: setattr(self.clues_lbl, 'height', self.clues_lbl.texture_size[1]))
        scroll.add_widget(self.clues_lbl)
        root.add_widget(scroll)

        self.grid_area = BoxLayout()
        root.add_widget(self.grid_area)

        chk = Button(text='Check Solution', size_hint_y=None, height=dp(48),
                     background_color=(0.20, 0.45, 0.75, 1), font_size=sp(17))
        chk.bind(on_press=self._check)
        root.add_widget(chk)
        self.add_widget(root)

    def new_puzzle(self):
        self._generate()
        self.clues_lbl.text = '\n\n'.join(f'Clue {i+1}: {c}' for i, c in enumerate(self.clues))
        self._build_grid()

    def _generate(self):
        t = random.choice(self.PUZZLE_TEMPLATES)
        self.categories = t['categories']
        self.items = t['items']

        c1 = list(self.items[self.categories[0]])
        c2 = list(self.items[self.categories[1]])
        c3 = list(self.items[self.categories[2]])
        random.shuffle(c2)
        random.shuffle(c3)

        self.solution = {}
        for i, p in enumerate(c1):
            self.solution[p] = {self.categories[1]: c2[i], self.categories[2]: c3[i]}
        self.sel = {p: {self.categories[1]: '', self.categories[2]: ''} for p in c1}

        p0, p1, p2 = c1
        self.clues = [
            f'{p0} has the {c2[0]}.',
            f'{p1} has the {c3[1]}.',
        ]
        wrong = [x for x in c2 if x != self.solution[p2][self.categories[1]]]
        if wrong:
            self.clues.append(f'{p2} does not have the {wrong[0]}.')
        assoc = self.solution[p2][self.categories[1]]
        target = self.solution[p2][self.categories[2]]
        self.clues.append(f'The person with the {assoc} has the {target}.')
        item = self.solution[p0][self.categories[2]]
        self.clues.append(f'Either {p0} or {p1} has the {item}.')
        wrong2 = [x for x in c3 if x != self.solution[p1][self.categories[2]]]
        if wrong2:
            self.clues.append(f'{p1} does not have the {wrong2[0]}.')

    def _build_grid(self):
        self.grid_area.clear_widgets()
        self.btns = {}
        persons = self.items[self.categories[0]]

        grid = GridLayout(cols=3, rows=len(persons) + 1, spacing=dp(2))
        grid.add_widget(Label(text=''))
        grid.add_widget(Label(text=self.categories[0], bold=True, font_size=sp(12), color=(0.15, 0.15, 0.45, 1)))
        for cat in self.categories[1:]:
            grid.add_widget(Label(text=cat, bold=True, font_size=sp(12), color=(0.15, 0.15, 0.45, 1)))

        for i, person in enumerate(persons):
            grid.add_widget(Label(text=str(i+1), font_size=sp(14)))
            grid.add_widget(Label(text=person, font_size=sp(13), color=(0, 0, 0.40, 1)))
            for cat in self.categories[1:]:
                btn = Button(text='?', font_size=sp(11), background_color=(0.90, 0.90, 0.92, 1))
                btn.bind(on_press=lambda _, p=person, c=cat: self._pick(p, c))
                self.btns[(person, cat)] = btn
                grid.add_widget(btn)

        self.grid_area.add_widget(grid)

    def _pick(self, person, cat):
        items_list = self.items[cat]
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        for item in items_list:
            b = Button(text=item, size_hint_y=None, height=dp(42))
            b.bind(on_press=lambda _, p=person, c=cat, v=item: self._set(p, c, v))
            content.add_widget(b)
        clr = Button(text='Clear', size_hint_y=None, height=dp(42), background_color=(0.70, 0.30, 0.30, 1))
        clr.bind(on_press=lambda _, p=person, c=cat: self._set(p, c, ''))
        content.add_widget(clr)
        self._sel_popup = Popup(title=f'{person} → {cat}', content=content, size_hint=(0.6, 0.55))
        self._sel_popup.open()

    def _set(self, person, cat, value):
        self.sel[person][cat] = value
        btn = self.btns[(person, cat)]
        btn.text = value if value else '?'
        btn.background_color = (0.70, 0.85, 1, 1) if value else (0.90, 0.90, 0.92, 1)
        self._sel_popup.dismiss()

    def _check(self, _=None):
        for p in self.sel:
            for c in self.sel[p]:
                if not self.sel[p][c]:
                    return self._popup('Incomplete', 'Fill all cells first!')
        for p in self.sel:
            for c in self.sel[p]:
                if self.sel[p][c] != self.solution[p][c]:
                    return self._popup('Incorrect', 'Some assignments are wrong — keep trying!')
        self._popup('🎉 Solved!', 'You cracked the Logic Grid!')

    def _popup(self, title, msg):
        Popup(title=title, content=Label(text=msg), size_hint=(0.7, 0.35)).open()


# ═══════════════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════════════

class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        root = BoxLayout(orientation='vertical', padding=dp(25), spacing=dp(12))

        root.add_widget(Label(text='🧩 Logic Puzzles', font_size=sp(34),
                              size_hint_y=None, height=dp(70), color=(0.12, 0.12, 0.45, 1)))
        root.add_widget(Label(text='Choose a puzzle to play', font_size=sp(15),
                              size_hint_y=None, height=dp(35), color=(0.50, 0.50, 0.50, 1)))

        puzzles = [
            ('🔲 Nonogram 5×5',  'nono5',   (0.18, 0.45, 0.75, 1)),
            ('🔲 Nonogram 10×10','nono10',  (0.15, 0.38, 0.68, 1)),
            ('💡 Lights Out 5×5','lo5',     (0.75, 0.55, 0.08, 1)),
            ('💡 Lights Out 7×7','lo7',     (0.68, 0.48, 0.05, 1)),
            ('🎯 Mastermind',    'mm',      (0.60, 0.15, 0.50, 1)),
            ('🧠 Logic Grid',    'logic',   (0.55, 0.18, 0.48, 1)),
            ('🔄 Random Puzzle', 'random',  (0.30, 0.30, 0.55, 1)),
            ('❓ How to Play',   'help',    (0.45, 0.45, 0.45, 1)),
        ]

        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=0.70)
        for text, key, color in puzzles:
            b = Button(text=text, font_size=sp(15), background_color=color, color=(1, 1, 1, 1))
            b.bind(on_press=lambda _, k=key: self._go(k))
            grid.add_widget(b)
        root.add_widget(grid)

        root.add_widget(Label(text='Train your brain with logic! 🧠', font_size=sp(12),
                              size_hint_y=None, height=dp(25), color=(0.55, 0.55, 0.55, 1)))
        self.add_widget(root)

    def _go(self, key):
        if key == 'help':
            self._show_help()
            return
            
        sm = self.manager
        mapping = {
            'nono5':  ('nono5',  lambda: NonogramScreen(5, name='nono5')),
            'nono10': ('nono10', lambda: NonogramScreen(10, name='nono10')),
            'lo5':    ('lo5',    lambda: LightsOutScreen(5, name='lo5')),
            'lo7':    ('lo7',    lambda: LightsOutScreen(7, name='lo7')),
            'mm':     ('mm',     lambda: MastermindScreen(name='mm')),
            'logic':  ('logic',  lambda: LogicGridScreen(name='logic')),
        }
        if key == 'random':
            key = random.choice(['nono5', 'lo5', 'mm', 'logic'])
        
        name, factory = mapping[key]
        if name not in sm.screen_names:
            sm.add_widget(factory())
        sm.current = name

    def _show_help(self):
        help_text = (
            "🔲 Nonogram: Fill cells to match row/column number clues. "
            "Use 'Mark ✕' for empty cells.\n\n"
            "💡 Lights Out: Tap a light to toggle it and its neighbours. Goal: all lights OFF.\n\n"
            "🎯 Mastermind: Guess the 4-color code. ● = right color & place, ○ = right color, wrong place.\n\n"
            "🧠 Logic Grid: Use the text clues to match people to their items."
        )
        Popup(title='How to Play', content=Label(text=help_text, font_size=sp(14)),
              size_hint=(0.85, 0.65)).open()


# ═══════════════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════════════

class LogicPuzzleApp(App):
    def build(self):
        Window.clearcolor = (0.95, 0.95, 0.97, 1)
        sm = ScreenManager(transition=SlideTransition(duration=0.25))
        sm.add_widget(MenuScreen(name='menu'))
        return sm


if __name__ == '__main__':
    LogicPuzzleApp().run()