import copy
from typing import List, Dict, Tuple, Optional
from rules.schemas import Player, Board, Coordinate, BOARD_SIZE

DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
]

def create_initial_board() -> Board:
    board = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    mid = BOARD_SIZE // 2
    board[mid - 1][mid - 1] = 'white'
    board[mid][mid] = 'white'
    board[mid - 1][mid] = 'black'
    board[mid][mid - 1] = 'black'
    return board

def is_on_board(r: int, c: int) -> bool:
    return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE

def get_valid_moves(board: Board, player: Player) -> List[Coordinate]:
    moves = []
    if not player: return moves
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if is_valid_move(board, player, r, c):
                moves.append(Coordinate(row=r, col=c))
    return moves

def is_valid_move(board: Board, player: Player, row: int, col: int) -> bool:
    if board[row][col] is not None: return False
    opponent = 'white' if player == 'black' else 'black'
    for dr, dc in DIRECTIONS:
        r, c = row + dr, col + dc
        found_opponent = False
        while is_on_board(r, c):
            cell = board[r][c]
            if cell == opponent: found_opponent = True
            elif cell == player:
                if found_opponent: return True
                break
            else: break
            r += dr
            c += dc
    return False

def apply_move(board: Board, player: Player, row: int, col: int) -> Board:
    new_board = copy.deepcopy(board)
    new_board[row][col] = player
    opponent = 'white' if player == 'black' else 'black'
    for dr, dc in DIRECTIONS:
        r, c = row + dr, col + dc
        to_flip = []
        while is_on_board(r, c):
            cell = new_board[r][c]
            if cell == opponent: to_flip.append((r, c))
            elif cell == player:
                for fr, fc in to_flip: new_board[fr][fc] = player
                break
            else: break
            r += dr
            c += dc
    return new_board

def count_score(board: Board) -> Dict[str, int]:
    return {
        "black": sum(row.count('black') for row in board),
        "white": sum(row.count('white') for row in board)
    }

def resolve_game_state(board: List[List[Optional[str]]], next_player: str) -> Tuple[bool, Optional[str], Optional[str], list]:
    """
    Evalúa el estado del tablero después de un movimiento.
    Devuelve: (game_over, winner, current_player, valid_moves)
    """
    valid_moves_next = get_valid_moves(board, next_player)
    
    if len(valid_moves_next) > 0:
        return False, None, next_player, valid_moves_next

    other_player = "white" if next_player == "black" else "black"
    valid_moves_other = get_valid_moves(board, other_player)
    
    if len(valid_moves_other) > 0:
        return False, None, other_player, valid_moves_other

    score = count_score(board)
    
    if score["black"] > score["white"]:
        winner = "black"
    elif score["white"] > score["black"]:
        winner = "white"
    else:
        winner = "draw" # Empate
        
    return True, winner, None, []