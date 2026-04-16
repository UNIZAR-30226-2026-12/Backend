import random
from typing import List, Optional, Set, Tuple

# Lista oficial de las 12 habilidades
SKILLS_LIST = [
    "gravity",       # 1. Gravedad (eliges dirección)
    "bomb",          # 2. Bomba 3x3
    "fix_piece",     # 3. Poner ficha fija
    "unfix_piece",   # 4. Quitar ficha fija
    "place_free",    # 5. Ficha libre
    "skip_rival",    # 6. Saltar turno rival
    "lose_turn",     # 7. Pierdes tu turno
    "flip_rival",    # 8. Voltear ficha rival
    "swap_colors",   # 9. Intercambio de color
    "steal_skill",   # 10. Robar habilidad
    "exchange_skill",# 11. Intercambiar habilidad
    "give_skill"     # 12. Dar habilidad
]

def get_random_skill() -> str:
    return random.choice(SKILLS_LIST)

def apply_gravity(board: List[List[Optional[str]]], direction: str, fixed_pieces: Set[Tuple[int, int]]) -> List[List[Optional[str]]]:
    """Desplaza todas las fichas en una dirección excepto las fijas."""
    size = len(board)
    new_board = [[None for _ in range(size)] for _ in range(size)]
    
    # Primero colocamos las fijas en su sitio exacto
    for r, c in fixed_pieces:
        new_board[r][c] = board[r][c]

    # Direcciones: (dr, dc)
    move_map = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    dr, dc = move_map[direction]

    # Creamos una lista de fichas moviles por procesar
    mobile_pieces = []
    for r in range(size):
        for c in range(size):
            if board[r][c] is not None and (r, c) not in fixed_pieces:
                mobile_pieces.append((r, c, board[r][c]))

    # Ordenamos segun la direccion para no solaparnos (ej: si es 'down', procesamos de abajo a arriba)
    if direction == "down": mobile_pieces.sort(key=lambda x: x[0], reverse=True)
    elif direction == "up": mobile_pieces.sort(key=lambda x: x[0])
    elif direction == "right": mobile_pieces.sort(key=lambda x: x[1], reverse=True)
    elif direction == "left": mobile_pieces.sort(key=lambda x: x[1])

    for r, c, color in mobile_pieces:
        curr_r, curr_c = r, c
        while True:
            next_r, next_c = curr_r + dr, curr_c + dc
            # Si se sale del tablero o choca con otra ficha (ya sea fija o recien movida), se para
            if not (0 <= next_r < size and 0 <= next_c < size) or new_board[next_r][next_c] is not None:
                new_board[curr_r][curr_c] = color
                break
            curr_r, curr_c = next_r, next_c
            
    return new_board

def apply_bomb(board: List[List[Optional[str]]], row: int, col: int, player_color: str) -> List[List[Optional[str]]]:
    """Voltea todas las fichas en un área 3x3 al color del jugador."""
    size = len(board)
    for r in range(max(0, row-1), min(size, row+2)):
        for c in range(max(0, col-1), min(size, col+2)):
            if board[r][c] is not None:
                board[r][c] = player_color
    return board

def swap_player_colors(board: List[List[Optional[str]]], p1: str, p2: str) -> List[List[Optional[str]]]:
    """Intercambia todas las fichas del tablero entre dos jugadores."""
    size = len(board)
    for r in range(size):
        for c in range(size):
            if board[r][c] == p1: board[r][c] = p2
            elif board[r][c] == p2: board[r][c] = p1
    return board

# Helpers sencillos para consistencia
def apply_free_place(board: List[List[Optional[str]]], r: int, c: int, color: str):
    if board[r][c] is None:
        board[r][c] = color
    return board

def apply_flip_rival(board: List[List[Optional[str]]], r: int, c: int, color: str, fixed_pieces: Set[Tuple[int, int]]):
    if board[r][c] is not None and (r, c) not in fixed_pieces:
        board[r][c] = color
    return board
