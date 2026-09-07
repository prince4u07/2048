"""Single entry point — run the project directly with `python main.py`."""
import argparse
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    core = _load('game2048_core', '2048.py')
    p = argparse.ArgumentParser(description='2048 — BFS / DFS / A* AI Edition')
    p.add_argument('--cli', action='store_true', help='console menu instead of GUI')
    p.add_argument('--compare', action='store_true', help='compare all 3 algorithms and exit')
    p.add_argument('--algo', choices=['BFS', 'DFS', 'A*'], help='run one algorithm headless')
    p.add_argument('--moves', type=int, default=30, help='moves for headless run (default 30)')
    p.add_argument('--depth', type=int, default=2, help='AI search depth (default 2)')
    args = p.parse_args()

    if args.compare:
        core.GameRunner().compare_all(num_moves=args.moves)
    elif args.algo:
        game = core.Game2048()
        solver = {'BFS': core.BFSSolver2048, 'DFS': core.DFSSolver2048,
                  'A*': core.AStarSolver2048}[args.algo](game)
        for i in range(args.moves):
            if game.is_game_over():
                break
            game.move(solver.best_move(search_depth=args.depth))
        game.display()
        print(f'{args.algo}: score={game.score} moves={game.moves_count}')
    elif args.cli:
        core.main()
    else:
        gui = _load('game2048_gui', '2048_gui.py')
        gui.main()


if __name__ == '__main__':
    main()
