"""2048 core engine + BFS / DFS / A* solvers that work together."""
import random
import heapq
import time
from collections import deque
from copy import deepcopy


class Game2048:
    """Core 2048 game engine."""

    def __init__(self, size=4):
        self.size = size
        self.board = [[0] * size for _ in range(size)]
        self.score = 0
        self.moves_count = 0
        self.add_random_tile()
        self.add_random_tile()

    def add_random_tile(self):
        empty = [(i, j) for i in range(self.size)
                 for j in range(self.size) if self.board[i][j] == 0]
        if empty:
            i, j = random.choice(empty)
            self.board[i][j] = 4 if random.random() < 0.1 else 2

    @staticmethod
    def _merge_left(row):
        non_zero = [x for x in row if x != 0]
        merged, gained, skip = [], 0, False
        for i, val in enumerate(non_zero):
            if skip:
                skip = False
                continue
            if i + 1 < len(non_zero) and non_zero[i] == non_zero[i + 1]:
                merged.append(val * 2)
                gained += val * 2
                skip = True
            else:
                merged.append(val)
        merged += [0] * (len(row) - len(merged))
        return merged, gained

    def move(self, direction):
        """Move: 0=up, 1=right, 2=down, 3=left. Returns True if board changed."""
        new_board, gained = simulate_move(self.board, direction)
        if new_board == self.board:
            return False
        self.board = new_board
        self.score += gained
        self.moves_count += 1
        self.add_random_tile()
        return True

    def is_game_over(self):
        if any(0 in row for row in self.board):
            return False
        for i in range(self.size):
            for j in range(self.size):
                val = self.board[i][j]
                if (j + 1 < self.size and self.board[i][j + 1] == val) or \
                   (i + 1 < self.size and self.board[i + 1][j] == val):
                    return False
        return True

    def get_max_tile(self):
        return max(max(row) for row in self.board)

    def display(self):
        for row in self.board:
            print(' '.join(f'{x:5}' for x in row))
        print(f"Score: {self.score} | Moves: {self.moves_count}\n")


def rotate_cw(board):
    return [list(row) for row in zip(*board[::-1])]


def rotate_ccw(board):
    return [list(row) for row in zip(*board)][::-1]


def simulate_move(board, direction):
    """Pure simulation: returns (new_board, score_gained). No random tile added."""
    size = len(board)
    if direction == 0:  # up
        tmp = rotate_ccw(board)
    elif direction == 1:  # right
        tmp = [row[::-1] for row in board]
    elif direction == 2:  # down
        tmp = rotate_cw(board)
    else:  # left
        tmp = [row[:] for row in board]
    new_rows, gained = [], 0
    for row in tmp:
        merged, g = Game2048._merge_left(row)
        new_rows.append(merged)
        gained += g
    if direction == 0:
        new_board = rotate_cw(new_rows)
    elif direction == 1:
        new_board = [row[::-1] for row in new_rows]
    elif direction == 2:
        new_board = rotate_ccw(new_rows)
    else:
        new_board = new_rows
    _ = size
    return new_board, gained


def evaluate_board(board):
    """Single shared heuristic for BFS, DFS and A*."""
    empty = sum(1 for row in board for cell in row if cell == 0)
    max_val = max(max(row) for row in board)
    monotonic = 0
    for row in board:
        for i in range(len(row) - 1):
            if row[i] > 0 and row[i + 1] > 0 and row[i] >= row[i + 1]:
                monotonic += 1
    return (empty * 150) + (max_val * 5) + (monotonic * 40)


class BFSSolver2048:
    """Breadth-First Search: explores level by level."""

    def __init__(self, game):
        self.game = game
        self.nodes_explored = 0

    def best_move(self, search_depth=2):
        queue = deque()
        for direction in range(4):
            nb, _ = simulate_move(self.game.board, direction)
            if nb != self.game.board:
                queue.append((nb, 1, direction))
        if not queue:
            return 0
        best_dir, best_score = queue[0][2], -float('inf')
        visited = set()
        self.nodes_explored = 0
        while queue:
            board, depth, first = queue.popleft()
            key = tuple(tuple(r) for r in board)
            if key in visited:
                continue
            visited.add(key)
            self.nodes_explored += 1
            score = evaluate_board(board)
            if score > best_score:
                best_score, best_dir = score, first
            if depth < search_depth:
                for d in range(4):
                    nb, _ = simulate_move(board, d)
                    if nb != board:
                        queue.append((nb, depth + 1, first))
        return best_dir


class DFSSolver2048:
    """Depth-First Search: explores each branch to max depth first."""

    def __init__(self, game):
        self.game = game
        self.nodes_explored = 0

    def best_move(self, search_depth=2):
        self.nodes_explored = 0
        visited = set()
        best = {'score': -float('inf'), 'dir': 0}
        for direction in range(4):
            nb, _ = simulate_move(self.game.board, direction)
            if nb != self.game.board:
                self._dfs(nb, 1, search_depth, direction, visited, best)
        return best['dir']

    def _dfs(self, board, depth, max_depth, first, visited, best):
        key = tuple(tuple(r) for r in board)
        if key in visited:
            return
        visited.add(key)
        self.nodes_explored += 1
        score = evaluate_board(board)
        if score > best['score']:
            best['score'], best['dir'] = score, first
        if depth < max_depth:
            for d in range(4):
                nb, _ = simulate_move(board, d)
                if nb != board:
                    self._dfs(nb, depth + 1, max_depth, first, visited, best)


class AStarSolver2048:
    """A*: best-first search ordered by heuristic (f = h - depth penalty)."""

    def __init__(self, game):
        self.game = game
        self.nodes_explored = 0

    def best_move(self, search_depth=2):
        heap = []
        for direction in range(4):
            nb, _ = simulate_move(self.game.board, direction)
            if nb != self.game.board:
                h = evaluate_board(nb)
                heapq.heappush(heap, (-h, 1, direction, nb))
        if not heap:
            return 0
        best_dir, best_score = heap[0][2], -float('inf')
        visited = set()
        self.nodes_explored = 0
        while heap:
            neg_h, depth, first, board = heapq.heappop(heap)
            key = tuple(tuple(r) for r in board)
            if key in visited:
                continue
            visited.add(key)
            self.nodes_explored += 1
            h = -neg_h
            if h > best_score:
                best_score, best_dir = h, first
            if depth < search_depth:
                for d in range(4):
                    nb, _ = simulate_move(board, d)
                    if nb != board:
                        h2 = evaluate_board(nb)
                        # depth penalty keeps search admissible-ish
                        heapq.heappush(heap, (-(h2 - depth * 10), depth + 1, first, nb))
        return best_dir


class GameRunner:
    """Run games with different solvers and compare them together."""

    def __init__(self):
        self.move_names = ['UP', 'RIGHT', 'DOWN', 'LEFT']
        self.solvers = {'BFS': BFSSolver2048, 'DFS': DFSSolver2048, 'A*': AStarSolver2048}

    def play_single(self, algorithm='BFS', num_moves=30):
        game = Game2048()
        solver = self.solvers[algorithm](game)
        print(f"\n{'=' * 50}\n2048 Game - {algorithm} Solver\n{'=' * 50}\n")
        game.display()
        start = time.time()
        for i in range(num_moves):
            if game.is_game_over():
                print(f"\nGame Over! Final Score: {game.score}")
                break
            move = solver.best_move(search_depth=2)
            game.move(move)
            print(f"Move {i + 1}: {self.move_names[move]:5} | "
                  f"Score: {game.score:6} | Nodes: {solver.nodes_explored}")
            if (i + 1) % 10 == 0:
                game.display()
        elapsed = time.time() - start
        print(f"\n{'=' * 50}\nAlgorithm: {algorithm} | Score: {game.score} | "
              f"Moves: {game.moves_count} | Time: {elapsed:.2f}s\n{'=' * 50}\n")
        return {'algorithm': algorithm, 'score': game.score,
                'moves': game.moves_count, 'time': elapsed}

    def compare_all(self, num_moves=20):
        results = [self.play_single(a, num_moves) for a in ['BFS', 'DFS', 'A*']]
        print(f"\n{'=' * 60}\nCOMPARISON RESULTS\n{'=' * 60}")
        print(f"{'Algorithm':<12} {'Score':<10} {'Moves':<10} {'Time(s)':<10}")
        print('-' * 60)
        for r in results:
            print(f"{r['algorithm']:<12} {r['score']:<10} {r['moves']:<10} {r['time']:<10.3f}")
        best = max(results, key=lambda r: r['score'])
        print(f"{'-' * 60}\nBest Algorithm: {best['algorithm']} "
              f"(Score: {best['score']})\n{'=' * 60}\n")


def launch_gui():
    """Launch the graphical 2048 interface (2048_gui.py)."""
    import importlib.util
    import os
    gui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2048_gui.py')
    if not os.path.isfile(gui_path):
        print("2048_gui.py not found next to this file.")
        return
    spec = importlib.util.spec_from_file_location('game2048_gui', gui_path)
    gui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gui)
    gui.main()


def main():
    runner = GameRunner()
    while True:
        print("\n" + "=" * 50)
        print("2048 - BFS, DFS, A* Comparison")
        print("=" * 50)
        print("0. Launch GUI")
        print("1. Play with BFS")
        print("2. Play with DFS")
        print("3. Play with A*")
        print("4. Compare All Algorithms")
        print("5. Exit")
        print("=" * 50)
        choice = input("Select option (0-5): ").strip()
        if choice == '0':
            launch_gui()
        elif choice == '1':
            runner.play_single('BFS', num_moves=50)
        elif choice == '2':
            runner.play_single('DFS', num_moves=50)
        elif choice == '3':
            runner.play_single('A*', num_moves=50)
        elif choice == '4':
            runner.compare_all(num_moves=30)
        elif choice == '5':
            print("Goodbye!")
            break
        else:
            print("Invalid choice!")


if __name__ == "__main__":
    main()
