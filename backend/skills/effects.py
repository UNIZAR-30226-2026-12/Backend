from typing import List, Optional, Set, Tuple

def apply_gravity(
    board: List[List[Optional[str]]], 
    direction: str, 
    fixed_pieces: Set[Tuple[int, int]],
    question_cells: List[List[int]]
) -> Tuple[List[List[Optional[str]]], List[List[int]]]:
    """Desplaza todas las fichas e interrogantes en una dirección excepto las fijas."""
    size = len(board)
    new_board = [[None for _ in range(size)] for _ in range(size)]
    
    # Primero colocamos las fijas en su sitio exacto
    for r, c in fixed_pieces:
        new_board[r][c] = board[r][c]

    # Direcciones: (dr, dc)
    move_map = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    dr, dc = move_map[direction]

    # Objetos moviles: (tipo, r, c, info)
    # Tipo puede ser 'piece' o 'question'
    mobile_objects = []
    
    # Recoger fichas
    for r in range(size):
        for c in range(size):
            if board[r][c] is not None and (r, c) not in fixed_pieces:
                mobile_objects.append({'type': 'piece', 'r': r, 'c': c, 'color': board[r][c]})
    
    # Recoger interrogantes (asegurándonos de que no haya una fija ahí, aunque no debería)
    q_set = {tuple(q) for q in question_cells}
    for qr, qc in q_set:
        if (qr, qc) not in fixed_pieces:
            mobile_objects.append({'type': 'question', 'r': qr, 'c': qc})

    # Ordenamos segun la direccion para procesar los que estan "mas cerca" del borde primero
    if direction == "down": mobile_objects.sort(key=lambda x: x['r'], reverse=True)
    elif direction == "up": mobile_objects.sort(key=lambda x: x['r'])
    elif direction == "right": mobile_objects.sort(key=lambda x: x['c'], reverse=True)
    elif direction == "left": mobile_objects.sort(key=lambda x: x['c'])

    new_question_cells = []
    
    # Mapa de ocupacion de la nueva tabla (incluyendo interrogantes)
    # Usamos un set para las posiciones ocupadas en new_board por piezas
    # Y otro para los interrogantes movidos
    occupied_by_piece = set(fixed_pieces)
    occupied_by_anything = set(fixed_pieces)

    for obj in mobile_objects:
        curr_r, curr_c = obj['r'], obj['c']
        while True:
            next_r, next_c = curr_r + dr, curr_c + dc
            if not (0 <= next_r < size and 0 <= next_c < size) or (next_r, next_c) in occupied_by_anything:
                if obj['type'] == 'piece':
                    new_board[curr_r][curr_c] = obj['color']
                    occupied_by_piece.add((curr_r, curr_c))
                    occupied_by_anything.add((curr_r, curr_c))
                else:
                    new_question_cells.append([curr_r, curr_c])
                    occupied_by_anything.add((curr_r, curr_c))
                break
            curr_r, curr_c = next_r, next_c
            
    return new_board, new_question_cells

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

def apply_free_place(board: List[List[Optional[str]]], r: int, c: int, color: str):
    """Colocación libre de ficha."""
    if board[r][c] is None:
        board[r][c] = color
    return board

def apply_flip_rival(board: List[List[Optional[str]]], r: int, c: int, color: str, fixed_pieces: Set[Tuple[int, int]]):
    """Volteo de ficha rival."""
    if board[r][c] is not None and (r, c) not in fixed_pieces:
        board[r][c] = color
    return board
