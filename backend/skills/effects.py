import random
from typing import List, Optional, Set, Tuple

def apply_gravity(
    board: List[List[Optional[str]]],
    direction: str,
    fixed_pieces: Set[Tuple[int, int]],
    question_cells: List[List[int]]
) -> Tuple[List[List[Optional[str]]], List[List[int]]]:
    """
    Desplaza todas las fichas no fijas en una dirección.
    Los interrogantes (skill_tiles) son FIJOS: no se mueven.
    Las fichas pueden caer encima de una casilla de interrogante sin problema.
    """
    size = len(board)
    new_board = [[None for _ in range(size)] for _ in range(size)]

    # Colocamos las fichas fijas en su sitio original
    for r, c in fixed_pieces:
        new_board[r][c] = board[r][c]

    move_map = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    dr, dc = move_map[direction]

    # Recoger solo fichas móviles (no fijas, no interrogantes)
    mobile_pieces = [
        {'r': r, 'c': c, 'color': board[r][c]}
        for r in range(size)
        for c in range(size)
        if board[r][c] is not None and (r, c) not in fixed_pieces
    ]

    # Ordenar: las más cercanas al borde destino se procesan primero
    if direction == "down":   mobile_pieces.sort(key=lambda x: x['r'], reverse=True)
    elif direction == "up":   mobile_pieces.sort(key=lambda x: x['r'])
    elif direction == "right": mobile_pieces.sort(key=lambda x: x['c'], reverse=True)
    elif direction == "left": mobile_pieces.sort(key=lambda x: x['c'])

    # Solo las fichas fijas bloquean el movimiento; los interrogantes NO bloquean
    occupied = set(fixed_pieces)

    for piece in mobile_pieces:
        curr_r, curr_c = piece['r'], piece['c']
        while True:
            next_r, next_c = curr_r + dr, curr_c + dc
            if not (0 <= next_r < size and 0 <= next_c < size) or (next_r, next_c) in occupied:
                new_board[curr_r][curr_c] = piece['color']
                occupied.add((curr_r, curr_c))
                break
            curr_r, curr_c = next_r, next_c

    # Los interrogantes NO se mueven: se devuelven sin cambios
    return new_board, question_cells

def apply_bomb(board: List[List[Optional[str]]], row: int, col: int, player_color: str, fixed_pieces: Set[Tuple[int, int]], mode: str, active_players: List[str]) -> List[List[Optional[str]]]:
    """Voltea todas las fichas en un área 3x3 al color del jugador."""
    size = len(board)
    if mode is not None and mode.replace("_skills", "") in ("1v1v1v1", "1vs1vs1vs1"):
        counts = {p: 0 for p in active_players}
        for r in range(size):
            for c in range(size):
                if board[r][c] in counts:
                    counts[board[r][c]] += 1
                    
        min_pieces = min(counts.values())
        candidates = [p for p, count in counts.items() if count == min_pieces]
        target_color_for_own = random.choice(candidates)
    else:
        target_color_for_own = "white" if player_color == "black" else "black"

    for r in range(max(0, row-1), min(size, row+2)):
        for c in range(max(0, col-1), min(size, col+2)):
            if board[r][c] is not None and (r, c) not in fixed_pieces:
                if board[r][c] != player_color:
                    board[r][c] = player_color
                else:
                    board[r][c] = target_color_for_own
    return board

def swap_player_colors(board: List[List[Optional[str]]], p1: str, p2: str, fixed_pieces: Set[Tuple[int, int]] = None) -> List[List[Optional[str]]]:
    """Intercambia todas las fichas del tablero entre dos jugadores. Las fichas fijas NO cambian de color."""
    if fixed_pieces is None: fixed_pieces = set()
    size = len(board)
    for r in range(size):
        for c in range(size):
            if (r, c) in fixed_pieces: continue
            if board[r][c] == p1: board[r][c] = p2
            elif board[r][c] == p2: board[r][c] = p1
    return board

def apply_free_place(board: List[List[Optional[str]]], r: int, c: int, color: str):
    """Colocación libre de ficha."""
    if board[r][c] is None:
        board[r][c] = color
    return board

def apply_flip_rival(board: List[List[Optional[str]]], r: int, c: int, color: str, fixed_pieces: Set[Tuple[int, int]]):
    """Volteo de ficha rival. Las fichas fijas pueden cambiar de color (pero siguen siendo fijas)."""
    if board[r][c] is not None:
        board[r][c] = color
    return board
