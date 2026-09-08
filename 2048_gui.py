"""
2048 — AI Lab Edition (BFS / DFS / A*)
Modern Tkinter interface: animated board, AI pilot panel, tournament mode.
Run:  python main.py  |  python 2048_gui.py
"""
import importlib.util
import json
import os
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_PATH = os.path.join(_DIR, '2048.py')
_BEST_PATH = os.path.join(_DIR, 'best_score.json')


def _load_core():
    spec = importlib.util.spec_from_file_location('game2048_core', _CORE_PATH)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core


_core = _load_core()
Game2048 = _core.Game2048
SOLVER_CLASSES = {'BFS': _core.BFSSolver2048,
                  'DFS': _core.DFSSolver2048,
                  'A*': _core.AStarSolver2048}
ALGORITHMS = list(SOLVER_CLASSES)
MOVE_NAMES = ['UP', 'RIGHT', 'DOWN', 'LEFT']
MOVE_ARROWS = ['↑', '→', '↓', '←']
ALGO_BLURB = {
    'BFS': 'Level-by-level search. Safe, balanced.',
    'DFS': 'Dives deep down one line. Aggressive.',
    'A*': 'Best-first on heuristic. Smartest.',
}
ALGO_COLOR = {'BFS': '#4d9eff', 'DFS': '#f2a541', 'A*': '#68b36a'}

THEMES = {
    'light': {
        'bg': '#faf8ef', 'panel': '#ffffff', 'panel_edge': '#e2dccd',
        'board': '#bbada0', 'empty': '#cdc1b4', 'ink': '#776e65',
        'muted': '#9a8f7f', 'tile_ink': '#776e65', 'tile_ink_light': '#f9f6f2',
        'overlay': '#faf8ef', 'accent_soft': '#fbe9e1',
    },
    'dark': {
        'bg': '#1d1f26', 'panel': '#262932', 'panel_edge': '#3a3f4d',
        'board': '#14161b', 'empty': '#2b2f3a', 'ink': '#f0ead9',
        'muted': '#8b90a0', 'tile_ink': '#776e65', 'tile_ink_light': '#ffffff',
        'overlay': '#1d1f26', 'accent_soft': '#33272a',
    },
}
TILE_COLORS = {
    2: '#eee4da', 4: '#ede0c8', 8: '#f2b179', 16: '#f59563',
    32: '#f67c5f', 64: '#f65e3b', 128: '#edcf72', 256: '#edcc61',
    512: '#edc850', 1024: '#edc53f', 2048: '#edc22e',
    4096: '#5fca9d', 8192: '#4fb3e8', 16384: '#8a7cf5',
}
SUPER_TILE = '#3c3a32'
ACCENT = '#e85d3d'


class Game2048UI:
    CELL = 100
    GAP = 10
    PAD = 12
    RADIUS = 10

    def __init__(self, root):
        self.root = root
        self.root.title('2048 · AI Lab — BFS / DFS / A*')
        self.theme_name = 'light'
        self.T = THEMES['light']

        self.game = Game2048()
        self.size = self.game.size
        self.history = []
        self.best_score = self.load_best()
        self.auto_playing = False
        self.solver = None
        self.win_celebrated = False
        self._overlay_ids = []
        self._overlay_widgets = []
        self._timers = []
        self._hl = set()
        self._gained = 0
        self.last_move = '–'
        self.last_nodes = 0
        self.disp_score = 0

        self.score_var = tk.StringVar(value='0')
        self.best_var = tk.StringVar(value=str(self.best_score))
        self.moves_var = tk.StringVar(value='0')
        self.max_var = tk.StringVar(value='2')
        self.algo_var = tk.StringVar(value='A*')
        self.depth_var = tk.IntVar(value=3)
        self.speed_var = tk.IntVar(value=280)  # ms between AI moves
        self.status_var = tk.StringVar(value='Arrow keys / WASD or D-pad to play.')
        self.ai_var = tk.StringVar(value='AI idle.')
        self.theme_var = tk.StringVar(value='☾ Dark')
        self.tour_var = tk.StringVar(value='No tournament yet — run one below.')

        self._build()
        self._apply_theme()
        self.refresh()
        self.update_stats(instant=True)

    # ================= layout =================
    def _build(self):
        self.main = tk.Frame(self.root)
        self.main.pack(fill='both', expand=True, padx=14, pady=10)

        header = tk.Frame(self.main)
        header.pack(fill='x', pady=(0, 8))
        title_box = tk.Frame(header)
        title_box.pack(side='left')
        self.title_lbl = tk.Label(title_box, text='2048',
                                  font=('Segoe UI', 34, 'bold'))
        self.title_lbl.pack(anchor='w')
        self.sub_lbl = tk.Label(title_box, text='A I   L A B   ·   BFS   DFS   A*',
                                font=('Segoe UI', 9, 'bold'))
        self.sub_lbl.pack(anchor='w')

        self.cards = tk.Frame(header)
        self.cards.pack(side='right')
        self.card_vals = {}
        for key, var in (('SCORE', self.score_var), ('BEST', self.best_var),
                         ('MOVES', self.moves_var), ('MAX', self.max_var)):
            card = tk.Frame(self.cards, padx=10, pady=4,
                            highlightthickness=1)
            card.pack(side='left', padx=4)
            tk.Label(card, text=key, font=('Segoe UI', 8, 'bold')).pack()
            val = tk.Label(card, textvariable=var, font=('Segoe UI', 15, 'bold'))
            val.pack()
            self.card_vals[key] = card

        body = tk.Frame(self.main)
        body.pack(fill='both', expand=True)

        # ---- board side ----
        left = tk.Frame(body)
        left.pack(side='left', anchor='n')
        side = self.size * self.CELL + (self.size + 1) * self.GAP + 2 * self.PAD
        self.canvas = tk.Canvas(left, width=side, height=side,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        # progress toward 2048
        prow = tk.Frame(left, pady=8)
        prow.pack(fill='x')
        self.goal_lbl = tk.Label(prow, text='Road to 2048', font=('Segoe UI', 9, 'bold'))
        self.goal_lbl.pack(side='left')
        self.goal_var = tk.StringVar(value='2')
        tk.Label(prow, textvariable=self.goal_var, font=('Segoe UI', 9)).pack(side='right')
        self.goal_bar = ttk.Progressbar(prow, length=180, mode='determinate', maximum=11)
        self.goal_bar.pack(side='right', padx=8)

        # ---- side panel (scrollable so Start AI is never cut off) ----
        self.side_outer = tk.Frame(body, width=320)
        self.side_outer.pack(side='left', fill='y', padx=(14, 0))
        self.side_outer.pack_propagate(False)
        self.side_canvas = tk.Canvas(self.side_outer, highlightthickness=0, bd=0)
        self.side_scroll = ttk.Scrollbar(self.side_outer, orient='vertical',
                                         command=self.side_canvas.yview)
        self.side_canvas.configure(yscrollcommand=self.side_scroll.set)
        self.side_scroll.pack(side='right', fill='y')
        self.side_canvas.pack(side='left', fill='both', expand=True)
        self.side = tk.Frame(self.side_canvas)
        self._side_win = self.side_canvas.create_window((0, 0), window=self.side,
                                                        anchor='nw')
        self.side.bind('<Configure>',
                       lambda e: self.side_canvas.configure(
                           scrollregion=self.side_canvas.bbox('all')))
        self.side_canvas.bind('<Configure>',
                              lambda e: self.side_canvas.itemconfig(
                                  self._side_win, width=e.width))
        # mousewheel scrolling over the panel
        self.side_canvas.bind('<Enter>', lambda e: self._bind_wheel(True))
        self.side_canvas.bind('<Leave>', lambda e: self._bind_wheel(False))

        self.play_panel = self._section('PLAY')
        brow = tk.Frame(self.play_panel)
        brow.pack(fill='x', pady=2)
        self.new_btn = self._big_btn(brow, '＋ New Game', self.new_game, ACCENT)
        self.new_btn.pack(side='left', expand=True, fill='x')
        self.undo_btn = self._big_btn(brow, '↩ Undo', self.undo)
        self.undo_btn.pack(side='left', expand=True, fill='x', padx=(8, 0))
        brow2 = tk.Frame(self.play_panel)
        brow2.pack(fill='x', pady=(6, 0))
        self.theme_btn = self._big_btn(brow2, '☾ Dark', self.toggle_theme)
        self.theme_btn.pack(side='left', expand=True, fill='x')
        self.help_btn = self._big_btn(brow2, '? Help', self.show_help, bg='#6c757d')
        self.help_btn.pack(side='left', expand=True, fill='x', padx=(8, 0))
        # D-pad (3-col grid so UP sits centered over DOWN)
        pad = tk.Frame(self.play_panel)
        pad.pack(pady=8)
        pad.grid_columnconfigure(0, weight=1)
        pad.grid_columnconfigure(1, weight=1)
        pad.grid_columnconfigure(2, weight=1)
        self._pad_btn(pad, '↑', 0, 1, 0)
        self._pad_btn(pad, '←', 1, 0, 3)
        self._pad_btn(pad, '↓', 1, 1, 2)
        self._pad_btn(pad, '→', 1, 2, 1)

        self.ai_panel = self._section('AI PILOT')
        self.algo_btns = {}
        arow = tk.Frame(self.ai_panel)
        arow.pack(fill='x', pady=(2, 6))
        for a in ALGORITHMS:
            b = tk.Button(arow, text=a, font=('Segoe UI', 11, 'bold'),
                          relief='flat', bd=0, cursor='hand2', pady=8,
                          highlightthickness=2,
                          command=lambda a=a: self.pick_algo(a))
            b.pack(side='left', expand=True, fill='x', padx=3)
            b.bind('<Enter>', lambda e, a=a: self._algo_hover(a, True))
            b.bind('<Leave>', lambda e, a=a: self._algo_hover(a, False))
            self.algo_btns[a] = b
        self.blurb_var = tk.StringVar()
        self.blurb_lbl = tk.Label(self.ai_panel, textvariable=self.blurb_var,
                                  font=('Segoe UI', 9, 'italic'), wraplength=280,
                                  justify='left')
        self.blurb_lbl.pack(anchor='w', pady=(0, 8))
        self._slider(self.ai_panel, 'Search depth', self.depth_var, 1, 5,
                     self._on_depth, captions=('1 · quick look', '5 · deep think'))
        self.depth_lbl = tk.Label(self.ai_panel, font=('Segoe UI', 9, 'bold'))
        self.depth_lbl.pack(anchor='w', pady=(0, 6))
        self._slider(self.ai_panel, 'Move delay', self.speed_var, 60, 800,
                     self._on_speed, resolution=10,
                     captions=('brisk', 'leisurely'))
        self.speed_lbl = tk.Label(self.ai_panel, font=('Segoe UI', 9))
        self.speed_lbl.pack(anchor='w', pady=(0, 4))
        self.play_btn = self._big_btn(self.ai_panel, '▶  Start AI', self.toggle_auto_play,
                                      ALGO_COLOR['A*'])
        self.play_btn.pack(fill='x', pady=(8, 6))
        readout = tk.Frame(self.ai_panel, highlightthickness=1)
        readout.pack(fill='x')
        self.ai_stripe = tk.Label(readout, text=' ', width=1, font=('Segoe UI', 9))
        self.ai_stripe.pack(side='left', fill='y')
        self.ai_readout = tk.Label(readout, textvariable=self.ai_var,
                                   font=('Consolas', 9), wraplength=250,
                                   justify='left', padx=8, pady=6)
        self.ai_readout.pack(side='left', fill='x', expand=True)
        self._readout_frame = readout
        self.pick_algo('A*')
        self._on_depth()
        self._on_speed()

        self.tour_panel = self._section('TOURNAMENT · ALL 3 AT ONCE')
        self.tour_sub = tk.Label(self.tour_panel, textvariable=self.tour_var,
                                 font=('Segoe UI', 9), wraplength=280, justify='left')
        self.tour_sub.pack(anchor='w', pady=(0, 4))
        self.bars = {}
        self.bar_rows = {}
        for a in ALGORITHMS:
            r = tk.Frame(self.tour_panel)
            r.pack(fill='x', pady=3)
            dot = tk.Label(r, text='●', fg=ALGO_COLOR[a], font=('Segoe UI', 11))
            dot.pack(side='left')
            name = tk.Label(r, text=a, width=4, font=('Segoe UI', 9, 'bold'))
            name.pack(side='left')
            bar = ttk.Progressbar(r, length=150, mode='determinate', maximum=100,
                                  style=f'Tour{a}.Horizontal.TProgressbar')
            bar.pack(side='left', padx=6)
            lbl = tk.Label(r, text='–', font=('Consolas', 9), width=13, anchor='w')
            lbl.pack(side='left')
            self.bars[a] = (bar, lbl)
            self.bar_rows[a] = (r, name, dot)
        trow = tk.Frame(self.tour_panel)
        trow.pack(fill='x', pady=(6, 0))
        tk.Label(trow, text='Moves:', font=('Segoe UI', 9, 'bold')).pack(side='left')
        self.tour_moves = tk.IntVar(value=60)
        ttk.Combobox(trow, textvariable=self.tour_moves, values=[20, 40, 60, 100, 200],
                     state='readonly', width=5).pack(side='left', padx=6)
        self.tour_btn = self._big_btn(trow, 'Run tournament ▸', self.run_tournament)
        self.tour_btn.pack(side='left', padx=4)

        self.log_panel = self._section('MOVE LOG')
        logrow = tk.Frame(self.log_panel)
        logrow.pack(fill='x')
        self.log = tk.Listbox(logrow, height=5, relief='flat', activestyle='none',
                              highlightthickness=1, font=('Consolas', 9),
                              selectbackground=ACCENT, selectforeground='white')
        self.log.pack(side='left', fill='x', expand=True)
        logscroll = ttk.Scrollbar(logrow, orient='vertical', command=self.log.yview)
        logscroll.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=logscroll.set)
        tk.Button(self.log_panel, text='Clear log', relief='flat', bd=0,
                  cursor='hand2', font=('Segoe UI', 8),
                  command=lambda: self.log.delete(0, 'end')).pack(anchor='e', pady=(4, 0))

        foot = tk.Frame(self.main)
        foot.pack(fill='x', pady=(10, 0))
        self.status_lbl = tk.Label(foot, textvariable=self.status_var,
                                   font=('Segoe UI', 9))
        self.status_lbl.pack(side='left')
        self.hint_lbl = tk.Label(foot, text='U undo · N new · T theme · ? help · Space AI',
                                 font=('Segoe UI', 8))
        self.hint_lbl.pack(side='right')

        self._bind_keys()

    def _section(self, title):
        box = tk.LabelFrame(self.side, text=f'  {title}  ',
                            font=('Segoe UI', 9, 'bold'), padx=10, pady=8)
        box.pack(fill='x', pady=(0, 10))
        return box

    def _big_btn(self, parent, text, cmd, bg=None, w=None):
        base = bg or '#8f7a66'
        b = tk.Button(parent, text=text, command=cmd, relief='flat', bd=0,
                      cursor='hand2', padx=10, pady=7, font=('Segoe UI', 10, 'bold'),
                      fg='white', bg=base, activeforeground='white',
                      activebackground=self._hover(base), width=w)
        b._base_bg = base
        b.bind('<Enter>', lambda e, b=b: b.config(bg=self._hover(b._base_bg)))
        b.bind('<Leave>', lambda e, b=b: b.config(bg=b._base_bg))
        return b

    def _set_btn_bg(self, btn, color):
        btn._base_bg = color
        btn.config(bg=color, activebackground=self._hover(color))

    @staticmethod
    def _hover(color):
        table = {'#e85d3d': '#f06e4f', '#8f7a66': '#9f8b77',
                 '#68b36a': '#7cc47e', '#c2573b': '#d4684a',
                 '#4d9eff': '#6db0ff', '#f2a541': '#f5b566'}
        return table.get(str(color), str(color))

    def _pad_btn(self, parent, text, r, c, direction):
        b = tk.Button(parent, text=text, width=4, font=('Segoe UI', 13, 'bold'),
                      relief='flat', bd=0, cursor='hand2',
                      command=lambda: self.do_move(direction))
        b.grid(row=r, column=c, padx=3, pady=3)
        self._pad_style(b)
        return b

    def _pad_style(self, b):
        T = self.T
        b.config(bg=T['panel'], fg=T['ink'], activebackground=T['panel_edge'],
                 activeforeground=T['ink'],
                 highlightbackground=T['panel_edge'], highlightthickness=1)
        b.bind('<Enter>', lambda e, b=b: b.config(bg=self.T['panel_edge']))
        b.bind('<Leave>', lambda e, b=b: b.config(bg=self.T['panel']))

    def _slider(self, parent, label, var, frm, to, cmd, resolution=1,
                  captions=None):
        tk.Label(parent, text=label, font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        ttk.Scale(parent, from_=frm, to=to, variable=var,
                  command=lambda *_: cmd(),
                  style='Warm.Horizontal.TScale').pack(fill='x', pady=(2, 0))
        if captions:
            cap = tk.Frame(parent)
            cap.pack(fill='x', pady=(0, 2))
            tk.Label(cap, text=captions[0], font=('Segoe UI', 8)).pack(side='left')
            tk.Label(cap, text=captions[1], font=('Segoe UI', 8)).pack(side='right')
            self._caption_frames = getattr(self, '_caption_frames', []) + [cap]

    def _on_depth(self):
        d = self.depth_var.get()
        word = 'quick look' if d <= 2 else 'balanced' if d == 3 else 'deep think'
        self.depth_lbl.config(text=f'Depth {d} · {word}')

    def _on_speed(self):
        v = self.speed_var.get()
        word = 'brisk' if v < 200 else 'steady' if v < 450 else 'leisurely'
        self.speed_lbl.config(text=f'{v} ms between moves · {word}')

    def _style_ttk(self):
        T = self.T
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        trough = T['panel_edge']
        style.configure('Warm.Horizontal.TScale', background=T['bg'],
                        troughcolor=trough, borderwidth=0, sliderthickness=16,
                        lightcolor=ACCENT, darkcolor=ACCENT, gripcount=0,
                        sliderrelief='flat')
        style.configure('Goal.Horizontal.TProgressbar', background='#e8a020',
                        troughcolor=trough, borderwidth=0, thickness=10)
        for a in ALGORITHMS:
            tag = f'Tour{a}.Horizontal.TProgressbar'
            style.configure(tag, background=ALGO_COLOR[a],
                            troughcolor=trough, borderwidth=0, thickness=12)
        try:
            self.goal_bar.configure(style='Goal.Horizontal.TProgressbar')
        except Exception:
            pass

    # ================= theme =================
    def toggle_theme(self):
        self.theme_name = 'dark' if self.theme_name == 'light' else 'light'
        self._apply_theme()
        self.refresh()

    def _apply_theme(self):
        T = THEMES[self.theme_name]
        self.T = T
        self._style_ttk()
        self.root.configure(bg=T['bg'])
        self.main.configure(bg=T['bg'])
        for w in self.main.winfo_children():
            try:
                w.configure(bg=T['bg'])
            except Exception:
                pass
        self.title_lbl.configure(bg=T['bg'], fg=T['ink'])
        self.sub_lbl.configure(bg=T['bg'], fg=ALGO_COLOR[self.algo_var.get()])
        self.status_lbl.configure(bg=T['bg'], fg=T['muted'])
        try:
            self.hint_lbl.configure(bg=T['bg'], fg=T['muted'])
        except Exception:
            pass
        self.goal_lbl.configure(bg=T['bg'], fg=T['muted'])
        try:
            self.side_outer.configure(bg=T['bg'])
            self.side_canvas.configure(bg=T['bg'])
            self.side.configure(bg=T['bg'])
        except Exception:
            pass
        self.canvas.configure(bg=T['board'], highlightthickness=1,
                              highlightbackground=T['panel_edge'])
        for card in self.card_vals.values():
            card.configure(bg=T['panel'], highlightbackground=T['panel_edge'])
            for ch in card.winfo_children():
                ch.configure(bg=T['panel'],
                             fg=T['ink'] if 'bold' in str(ch.cget('font')) else T['muted'])
        for panel in (self.play_panel, self.ai_panel, self.tour_panel, self.log_panel):
            panel.configure(bg=T['bg'], fg=T['ink'])
            for ch in panel.winfo_children():
                self._paint(ch, T)
        self.log.configure(bg=T['panel'], fg=T['ink'],
                           highlightbackground=T['panel_edge'])
        self.theme_btn.config(text='☀ Light' if self.theme_name == 'dark' else '☾ Dark')
        self.pick_algo(self.algo_var.get())
        # restore hand-tuned details that the generic painter flattens
        try:
            self.blurb_lbl.config(fg=T['muted'])
            self.depth_lbl.config(fg=T['ink'])
            self.speed_lbl.config(fg=T['muted'])
            self.tour_sub.config(fg=T['ink'])
            self.ai_readout.config(bg=T['panel'], fg=T['ink'])
            self._readout_frame.config(bg=T['panel'],
                                       highlightbackground=T['panel_edge'])
            self.ai_stripe.config(bg=ALGO_COLOR[self.algo_var.get()])
            for a in ALGORITHMS:
                _, name, dot = self.bar_rows[a]
                dot.config(bg=T['bg'], fg=ALGO_COLOR[a])
                name.config(bg=T['bg'])
            for cap in getattr(self, '_caption_frames', []):
                cap.config(bg=T['bg'])
                for ch in cap.winfo_children():
                    ch.config(bg=T['bg'], fg=T['muted'])
        except Exception:
            pass

    def _paint(self, w, T):
        try:
            cls = w.winfo_class()
            if cls in ('Frame', 'Labelframe'):
                w.configure(bg=T['bg'])
            if cls == 'Label':
                # don't stomp on colored dots / buttons / readout
                try:
                    if w not in (getattr(self, 'ai_stripe', None),):
                        w.configure(bg=w.master.cget('bg'), fg=T['ink'])
                except Exception:
                    pass
        except Exception:
            pass
        for ch in w.winfo_children():
            # buttons manage their own colors (algo select, New Game, AI play)
            if ch.winfo_class() == 'Button':
                continue
            self._paint(ch, T)

    # ================= board drawing =================
    def _geom(self, r, c):
        x1 = self.PAD + self.GAP + c * (self.CELL + self.GAP)
        y1 = self.PAD + self.GAP + r * (self.CELL + self.GAP)
        return x1, y1, x1 + self.CELL, y1 + self.CELL

    def _round(self, x1, y1, x2, y2, grow=0, **kw):
        x1, y1, x2, y2 = x1 - grow, y1 - grow, x2 + grow, y2 + grow
        r = self.RADIUS
        pts = [x1 + r, y1, x2 - r, y1, x2, y1 + r, x2, y2 - r,
               x2 - r, y2, x1 + r, y2, x1, y2 - r, x1, y1 + r]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def refresh(self, pop_cells=()):
        for t in self._timers:
            try:
                self.root.after_cancel(t)
            except Exception:
                pass
        self._timers = []
        self.canvas.delete('all')
        self._overlay_ids = []
        T = self.T
        pop = set(pop_cells)
        for r in range(self.size):
            for c in range(self.size):
                v = self.game.board[r][c]
                x1, y1, x2, y2 = self._geom(r, c)
                if v == 0:
                    self._round(x1, y1, x2, y2, fill=T['empty'], outline='')
                else:
                    grow = 7 if (r, c) in pop else 0
                    glow = ACCENT if (r, c) in self._hl and v >= 128 else ''
                    if glow:
                        self._round(x1, y1, x2, y2, grow=3, fill=glow, outline='')
                    self._round(x1, y1, x2, y2, grow=grow,
                                fill=TILE_COLORS.get(v, SUPER_TILE), outline='')
                    fg = T['tile_ink'] if v <= 4 else T['tile_ink_light']
                    self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                                            text=str(v), fill=fg,
                                            font=('Segoe UI', self._font_size(v), 'bold'))
                    if (r, c) in self._hl and v < 128:
                        self.canvas.create_rectangle(x1 + 2, y1 + 2, x2 - 2, y2 - 2,
                                                     outline=ACCENT, width=3)
        if self._hl:
            self._timers.append(self.root.after(260, self._clear_flash))
        if pop:
            # settle the "pop" back to normal size shortly after
            self._timers.append(self.root.after(130, self._clear_flash))

    @staticmethod
    def _font_size(v):
        n = len(str(v))
        return {1: 44, 2: 40, 3: 32, 4: 26, 5: 22}.get(n, 20)

    def _clear_flash(self):
        self._hl = set()
        if self._overlay_ids:
            return  # win / game-over overlay is up — leave it alone
        self.refresh()

    def _float_text(self, text, x, y, color=ACCENT):
        # white halo first so the popup reads over any tile, then the color
        items = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            items.append(self.canvas.create_text(
                x + dx, y + dy, text=text, fill='white',
                font=('Segoe UI', 24, 'bold')))
        items.append(self.canvas.create_text(x, y, text=text, fill=color,
                                             font=('Segoe UI', 24, 'bold')))
        self._anim_float(items, 0)

    def _anim_float(self, items, step):
        try:
            for item in items:
                self.canvas.move(item, 0, -3)
            if step < 14:
                self._timers.append(self.root.after(
                    35, lambda: self._anim_float(items, step + 1)))
            else:
                for item in items:
                    self.canvas.delete(item)
        except Exception:
            pass

    # ================= gameplay =================
    def do_move(self, direction):
        if self.auto_playing or self._overlay_ids:
            return
        self._apply_move(direction)

    def _apply_move(self, direction, by_ai=False):
        old = [row[:] for row in self.game.board]
        old_score = self.game.score
        old_moves = self.game.moves_count
        if not self.game.move(direction):
            return False
        gained = self.game.score - old_score
        self._gained = gained
        self.history.append({'board': old, 'score': old_score, 'moves': old_moves})
        if len(self.history) > 300:
            self.history.pop(0)
        self.last_move = f'{MOVE_ARROWS[direction]} {MOVE_NAMES[direction]}'
        self._hl = {(r, c) for r in range(self.size) for c in range(self.size)
                    if (old[r][c] == 0 and self.game.board[r][c] in (2, 4))
                    or (old[r][c] and self.game.board[r][c] == old[r][c] * 2)}
        merged = sorted((r, c) for (r, c) in self._hl
                        if old[r][c] and self.game.board[r][c] == old[r][c] * 2)
        self.refresh(pop_cells=merged)
        if gained:
            # pop the "+N" right over the first merged tile, not the board edge
            if merged:
                r, c = merged[0]
                x1, y1, x2, y2 = self._geom(r, c)
                px, py = (x1 + x2) // 2, (y1 + y2) // 2
            else:
                px = self.canvas.winfo_width() // 2 or 260
                py = self.canvas.winfo_height() // 2 or 260
            self._float_text(f'+{gained}', px, py)
        self.update_stats()
        tag = self.algo_var.get() if by_ai else 'YOU'
        self._log(f'{tag:>4} {self.last_move:<8} +{gained:<5} = {self.game.score}')
        self.check_win()
        self.check_over()
        return True

    def _log(self, line):
        self.log.insert('end', line)
        self.log.see('end')
        while self.log.size() > 60:
            self.log.delete(0)

    def undo(self):
        if self.auto_playing or self._overlay_ids or not self.history:
            return
        s = self.history.pop()
        self.game.board = [row[:] for row in s['board']]
        self.game.score = s['score']
        self.game.moves_count = s['moves']
        self.disp_score = s['score']
        self.refresh()
        self.update_stats(instant=True)
        self.status_var.set('Undone — keep playing.')

    def new_game(self):
        self.stop_auto()
        self.hide_overlay()
        self.game = Game2048()
        self.history = []
        self.win_celebrated = False
        self._hl = set()
        self.last_move = '–'
        self.disp_score = 0
        self.log.delete(0, 'end')
        self.refresh()
        self.update_stats(instant=True)
        self.status_var.set('Fresh board — good luck, reach 2048!')

    def update_stats(self, instant=False):
        target = self.game.score
        if instant:
            self.disp_score = target
            self.score_var.set(str(target))
        elif self.disp_score != target:
            self._tween_score(target)
        else:
            self.score_var.set(str(target))
        self.moves_var.set(str(self.game.moves_count))
        try:
            mx = self.game.get_max_tile()
        except Exception:
            mx = max(max(r) for r in self.game.board)
        self.max_var.set(str(mx))
        if target > self.best_score:
            self.best_score = target
            self.best_var.set(str(self.best_score))
            self.save_best()
        # road-to-2048 progress (log2 scale, 2^1 .. 2^11)
        import math
        step = max(0, min(11, int(math.log2(max(mx, 2)))))
        self.goal_bar['value'] = step
        self.goal_var.set(f'{mx}  →  2048  ({step}/11)')

    def _tween_score(self, target):
        diff = target - self.disp_score
        step = max(1, abs(diff) // 6 + 1)
        self.disp_score += step if diff > 0 else -step
        if (diff > 0 and self.disp_score > target) or (diff < 0 and self.disp_score < target):
            self.disp_score = target
        self.score_var.set(str(self.disp_score))
        if self.disp_score != target:
            self._timers.append(self.root.after(25, lambda: self._tween_score(target)))

    # ================= keys / overlay =================
    def _bind_wheel(self, on):
        try:
            if on:
                self.side_canvas.bind_all('<MouseWheel>',
                                          self._on_wheel, add='+')
                self.side_canvas.bind_all('<Button-4>',
                                          self._on_wheel, add='+')
                self.side_canvas.bind_all('<Button-5>',
                                          self._on_wheel, add='+')
            else:
                self.side_canvas.unbind_all('<MouseWheel>')
                self.side_canvas.unbind_all('<Button-4>')
                self.side_canvas.unbind_all('<Button-5>')
        except Exception:
            pass

    def _on_wheel(self, e):
        try:
            if getattr(e, 'num', None) == 4:
                self.side_canvas.yview_scroll(-1, 'units')
            elif getattr(e, 'num', None) == 5:
                self.side_canvas.yview_scroll(1, 'units')
            else:
                self.side_canvas.yview_scroll(-1 * int(e.delta / 120), 'units')
        except Exception:
            pass
        return 'break'

    def _bind_keys(self):
        for keysym, d in (('Up', 0), ('Right', 1), ('Down', 2), ('Left', 3)):
            self.root.bind(f'<{keysym}>', lambda e, d=d: self.do_move(d))
        for ch, d in (('w', 0), ('d', 1), ('s', 2), ('a', 3),
                      ('k', 0), ('l', 1), ('j', 2), ('h', 3)):
            self.root.bind(f'<{ch}>', lambda e, d=d: self.do_move(d))
            self.root.bind(f'<{ch.upper()}>', lambda e, d=d: self.do_move(d))
        self.root.bind('<u>', lambda e: self.undo())
        self.root.bind('<U>', lambda e: self.undo())
        self.root.bind('<n>', lambda e: self.new_game())
        self.root.bind('<N>', lambda e: self.new_game())
        self.root.bind('<t>', lambda e: self.toggle_theme())
        self.root.bind('<T>', lambda e: self.toggle_theme())
        self.root.bind('<space>', lambda e: self.toggle_auto_play())
        self.root.bind('<?>', lambda e: self.show_help())
        self.root.bind('<F1>', lambda e: self.show_help())

    def show_help(self):
        messagebox.showinfo(
            'How to play',
            'Slide tiles with Arrow keys / WASD (or HJKL, or the D-pad).\n'
            'Equal tiles merge. Reach 2048 to win.\n\n'
            'U — undo   N — new game   T — theme\n'
            'Space — start/stop AI   F1 or ? — this help\n\n'
            'AI Pilot: pick BFS / DFS / A*, tune depth, then Start AI.\n'
            'Tournament races all three solvers headlessly.')

    def hide_overlay(self):
        for i in self._overlay_ids:
            try:
                self.canvas.delete(i)
            except tk.TclError:
                pass
        self._overlay_ids = []
        for w in getattr(self, '_overlay_widgets', []):
            try:
                w.destroy()
            except Exception:
                pass
        self._overlay_widgets = []

    def show_overlay(self, title, subtitle, color=ACCENT, keep_playing=True):
        # a pending tile-flash must not wipe the overlay a moment later
        for t in self._timers:
            try:
                self.root.after_cancel(t)
            except Exception:
                pass
        self._timers = []
        self._hl = set()
        self.hide_overlay()
        w = self.size * self.CELL + (self.size + 1) * self.GAP + 2 * self.PAD
        cx, cy = w // 2, w // 2
        self._overlay_ids.append(self.canvas.create_rectangle(
            self.PAD, self.PAD, w - self.PAD, w - self.PAD,
            fill=self.T['overlay'], stipple='gray50', outline=''))
        self._overlay_ids.append(self.canvas.create_text(
            cx, cy - 84, text=title, fill=color, font=('Segoe UI', 44, 'bold')))
        self._overlay_ids.append(self.canvas.create_text(
            cx, cy - 28, text=subtitle, fill=self.T['ink'], font=('Segoe UI', 12),
            width=w - 120, justify='center'))
        if keep_playing:
            again = tk.Button(self.canvas, text='New Game', bg=ACCENT, fg='white',
                              relief='flat', bd=0, cursor='hand2', padx=14, pady=7,
                              font=('Segoe UI', 11, 'bold'), command=self.new_game)
            self._overlay_widgets.append(again)
            self._overlay_ids.append(self.canvas.create_window(cx - 95, cy + 50, window=again))
            keep = tk.Button(self.canvas, text='Keep playing', bg='#8f7a66', fg='white',
                             relief='flat', bd=0, cursor='hand2', padx=14, pady=7,
                             font=('Segoe UI', 11, 'bold'), command=self.hide_overlay)
            self._overlay_widgets.append(keep)
            self._overlay_ids.append(self.canvas.create_window(cx + 95, cy + 50, window=keep))
        else:
            start = tk.Button(self.canvas, text='Start Game', bg=ACCENT, fg='white',
                              relief='flat', bd=0, cursor='hand2', padx=22, pady=9,
                              font=('Segoe UI', 13, 'bold'), command=self.new_game)
            self._overlay_widgets.append(start)
            self._overlay_ids.append(self.canvas.create_window(cx, cy + 55, window=start))

    def check_win(self):
        if self.win_celebrated:
            return
        if any(2048 in row for row in self.game.board):
            self.win_celebrated = True
            self.stop_auto()
            self.show_overlay('🏆 YOU WIN!', f'2048 reached · score {self.game.score}', '#e8a020')
            self.status_var.set('Champion — 2048! Keep going or start fresh.')

    def check_over(self):
        if self.game.is_game_over():
            self.stop_auto()
            self.show_overlay('GAME OVER',
                              f'score {self.game.score} · {self.game.moves_count} moves · max {self.max_var.get()}',
                              keep_playing=False)
            self.status_var.set('No moves left — hit Start Game.')

    # ================= persistence =================
    def load_best(self):
        try:
            with open(_BEST_PATH, 'r', encoding='utf-8') as fh:
                return int(json.load(fh).get('best', 0) or 0)
        except Exception:
            return 0

    def save_best(self):
        try:
            with open(_BEST_PATH, 'w', encoding='utf-8') as fh:
                json.dump({'best': self.best_score}, fh)
        except Exception:
            pass

    # ================= AI =================
    def pick_algo(self, algo):
        self.algo_var.set(algo)
        self.blurb_var.set(f'{algo} — {ALGO_BLURB[algo]}')
        idle_bg = '#ece5d8' if self.theme_name == 'light' else self.T['panel']
        for a, b in self.algo_btns.items():
            if a == algo:
                b.config(bg=ALGO_COLOR[a], fg='white',
                         activebackground=ALGO_COLOR[a], activeforeground='white',
                         highlightbackground=ALGO_COLOR[a])
            else:
                b.config(bg=idle_bg, fg=self.T['ink'],
                         activebackground=self.T['panel_edge'],
                         highlightbackground=self.T['panel_edge'])
        try:
            self.ai_stripe.config(bg=ALGO_COLOR[algo])
            self._readout_frame.config(highlightbackground=self.T['panel_edge'])
            if not self.auto_playing:
                self._set_btn_bg(self.play_btn, ALGO_COLOR[algo])
            self.sub_lbl.config(fg=ALGO_COLOR[algo])
        except Exception:
            pass
        if not self.auto_playing:
            self.ai_var.set(f'{algo} armed — press Start AI.')

    def _algo_hover(self, algo, entering):
        if algo == self.algo_var.get():
            return
        b = self.algo_btns[algo]
        if entering:
            b.config(bg=self.T['panel_edge'])
        else:
            idle = '#ece5d8' if self.theme_name == 'light' else self.T['panel']
            b.config(bg=idle)

    def toggle_auto_play(self):
        if self.auto_playing:
            self.stop_auto()
            self.status_var.set('AI stopped — your move.')
            return
        algo = self.algo_var.get()
        if algo not in SOLVER_CLASSES:
            return
        self.hide_overlay()
        self.solver = SOLVER_CLASSES[algo](self.game)
        self.auto_playing = True
        self._set_btn_bg(self.play_btn, '#c2573b')
        self.play_btn.config(text='■  Stop AI')
        self.status_var.set(f'{algo} autopilot · depth {self.depth_var.get()} · Space to stop.')
        self.root.after(80, self._ai_step)

    def stop_auto(self):
        if not self.auto_playing:
            return
        self.auto_playing = False
        try:
            self._set_btn_bg(self.play_btn, ALGO_COLOR[self.algo_var.get()])
            self.play_btn.config(text='▶  Start AI')
            self.ai_var.set(f'{self.algo_var.get()} idle — press Start AI.')
        except Exception:
            pass

    def _ai_step(self):
        if not self.auto_playing:
            return
        if self.game.is_game_over():
            self.check_over()
            return
        result, depth = {}, int(self.depth_var.get())

        def compute():
            try:
                result['move'] = self.solver.best_move(search_depth=depth)
                result['nodes'] = self.solver.nodes_explored
            except Exception as exc:
                result['error'] = exc

        threading.Thread(target=compute, daemon=True).start()

        def poll():
            if 'move' in result:
                if self.auto_playing:
                    self._apply_move(result['move'], by_ai=True)
                    self.last_nodes = result.get('nodes', 0)
                    self.ai_var.set(f'{self.algo_var.get()} · depth {depth} · '
                                    f'{self.last_move} · {self.last_nodes} nodes')
                if self.auto_playing and not self.game.is_game_over():
                    self.root.after(int(self.speed_var.get()), self._ai_step)
            elif 'error' in result:
                self.stop_auto()
                messagebox.showerror('Solver problem', str(result['error']))
            else:
                self.root.after(20, poll)

        self.root.after(20, poll)

    # ================= tournament =================
    def run_tournament(self):
        self.tour_btn.config(state='disabled')
        self.tour_var.set('Tournament running… watch the bars.')
        for a, (bar, lbl) in self.bars.items():
            bar['value'] = 0
            lbl.config(text='playing…')
        moves = int(self.tour_moves.get())

        def work():
            import time
            rows = []
            for algo in ALGORITHMS:
                g = Game2048()
                solver = SOLVER_CLASSES[algo](g)
                t0 = time.time()
                for _ in range(moves):
                    if g.is_game_over():
                        break
                    g.move(solver.best_move(search_depth=2))
                try:
                    mx = g.get_max_tile()
                except Exception:
                    mx = max(max(r) for r in g.board)
                rows.append((algo, g.score, g.moves_count, mx, time.time() - t0))
            self.root.after(0, lambda: self._tour_done(rows))

        threading.Thread(target=work, daemon=True).start()

    def _tour_done(self, rows):
        self.tour_btn.config(state='normal')
        top = max(r[1] for r in rows) or 1
        best = max(rows, key=lambda r: (r[1], r[3]))
        for algo, score, mv, mx, t in rows:
            bar, lbl = self.bars[algo]
            bar['value'] = 100 * score / top
            crown = ' *' if algo == best[0] else ''
            lbl.config(text=f'{score} {mv}mv {mx}{crown}')
            try:
                _, name, _ = self.bar_rows[algo]
                name.config(fg=ACCENT if algo == best[0] else self.T['ink'])
            except Exception:
                pass
        self.tour_var.set(f'Winner: {best[0]} — score {best[1]}, max tile {best[3]} '
                          f'in {best[2]} moves ({best[4]:.1f}s).')

    # ================= lifecycle =================
    def on_close(self):
        self.save_best()
        self.root.destroy()


def main():
    try:  # crisp text on Windows HiDPI
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    root.title('2048 · AI Lab — BFS / DFS / A*')
    try:
        f = tkfont.nametofont('TkDefaultFont')
        f.configure(family='Segoe UI', size=10)
    except Exception:
        pass
    style = ttk.Style()
    try:
        style.theme_use('clam')
    except Exception:
        pass
    app = Game2048UI(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    # center, but clamp to the actual screen so nothing is cut off
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    w = min(w, max(600, sw - 40))
    h = min(h, max(500, sh - 80))
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 3)
    root.geometry(f'{w}x{h}+{x}+{y}')
    root.minsize(760, 560)
    root.resizable(True, True)
    root.mainloop()


if __name__ == '__main__':
    main()
