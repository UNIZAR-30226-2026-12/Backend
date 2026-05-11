import copy
from typing import List, Dict, Tuple, Optional
from rules.schemas import Player, Board, Coordinate, BOARD_SIZE

# --- CONSTANTES 1V1 ---
DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
]

# --- CONSTANTES 4 JUGADORES ---
PIECES_4P = ["black", "white", "red", "blue"]
TURN_ORDER_4P = ["black", "white", "red", "blue"]
BOARD_SIZE_4P = 16
DIRECTIONS_4P = DIRECTIONS

# ==========================================
# LÓGICA 1 VS 1
# ==========================================

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

def get_valid_moves(board: Board, player: Player, fixed_pieces: set = None) -> List[Coordinate]:
    moves = []
    if not player:
        return moves
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if is_valid_move(board, player, r, c, fixed_pieces):
                moves.append(Coordinate(row=r, col=c))
    return moves

def is_valid_move(board: Board, player: Player, row: int, col: int, fixed_pieces: set = None) -> bool:
    if board[row][col] is not None:
        return False
    opponent = 'white' if player == 'black' else 'black'
    if fixed_pieces is None:
        fixed_pieces = set()
    for dr, dc in DIRECTIONS:
        r, c = row + dr, col + dc
        found_opponent = False
        while is_on_board(r, c):
            cell = board[r][c]
            if cell == opponent:
                if (r, c) in fixed_pieces:
                    found_opponent = False
                    break
                found_opponent = True
            elif cell == player:
                if found_opponent:
                    return True
                break
            else:
                break
            r += dr
            c += dc
    return False

def apply_move(board: Board, player: Player, row: int, col: int, fixed_pieces: set = None) -> Board:
    new_board = copy.deepcopy(board)
    new_board[row][col] = player
    opponent = 'white' if player == 'black' else 'black'
    if fixed_pieces is None:
        fixed_pieces = set()
    for dr, dc in DIRECTIONS:
        r, c = row + dr, col + dc
        to_flip = []
        possible_flip = False
        while is_on_board(r, c):
            cell = new_board[r][c]
            if cell == opponent:
                if (r, c) in fixed_pieces:
                    to_flip = []
                    break
                to_flip.append((r, c))
            elif cell == player:
                if to_flip:
                    possible_flip = True
                break
            else: 
                to_flip = []
                break
            r += dr
            c += dc
        if possible_flip:
            for fr, fc in to_flip:
                new_board[fr][fc] = player
    return new_board

def count_score(board: Board) -> Dict[str, int]:
    return {
        "black": sum(row.count('black') for row in board),
        "white": sum(row.count('white') for row in board)
    }

def resolve_game_state(board: List[List[Optional[str]]], next_player: str, fixed_pieces: set = None) -> Tuple[bool, Optional[str], Optional[str], list]:
    if fixed_pieces is None:
        fixed_pieces = set()
    valid_moves_next = get_valid_moves(board, next_player, fixed_pieces)
    if len(valid_moves_next) > 0:
        return False, None, next_player, valid_moves_next

    other_player = "white" if next_player == "black" else "black"
    valid_moves_other = get_valid_moves(board, other_player, fixed_pieces)
    if len(valid_moves_other) > 0:
        return False, None, other_player, valid_moves_other

    score = count_score(board)
    if score["black"] > score["white"]:
        winner = "black"
    elif score["white"] > score["black"]:
        winner = "white"
    else:
        winner = "draw"
        
    return True, winner, None, []

# ==========================================
# LÓGICA 4 JUGADORES (FFA)
# ==========================================

def create_initial_board_4p() -> List[List[Optional[str]]]:
    board = [[None for _ in range(BOARD_SIZE_4P)] for _ in range(BOARD_SIZE_4P)]
    top_row, bottom_row = 3, 11
    left_col, right_col = 3, 11

    def place_cluster(start_row: int, start_col: int, top_left: str, top_right: str, bottom_left: str, bottom_right: str):
        board[start_row][start_col] = top_left
        board[start_row][start_col + 1] = top_right
        board[start_row + 1][start_col] = bottom_left
        board[start_row + 1][start_col + 1] = bottom_right

    place_cluster(top_row, left_col, "black", "white", "red", "blue")
    place_cluster(top_row, right_col, "white", "black", "blue", "red")
    place_cluster(bottom_row, left_col, "red", "blue", "black", "white")
    place_cluster(bottom_row, right_col, "blue", "red", "white", "black")
    return board

def is_inside_4p(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE_4P and 0 <= col < BOARD_SIZE_4P

def get_flips_4p(board: List[List[Optional[str]]], row: int, col: int, piece: str, fixed_pieces: set = None) -> List[Tuple[int, int]]:
    if board[row][col] is not None:
        return []

    if fixed_pieces is None:
        fixed_pieces = set()
    flips: List[Tuple[int, int]] = []
    for dr, dc in DIRECTIONS_4P:
        line: List[Tuple[int, int]] = []
        r, c = row + dr, col + dc

        while is_inside_4p(r, c):
            cell = board[r][c]
            if cell is None:
                line = []
                break
            if cell != piece:
                if (r, c) in fixed_pieces:
                    line = []
                    break
                line.append((r, c))
                r += dr
                c += dc
                continue
            break

        if line and is_inside_4p(r, c) and board[r][c] == piece:
            flips.extend(line)

    return flips

def get_valid_moves_4p(board: List[List[Optional[str]]], piece: str, fixed_pieces: set = None) -> List[Dict[str, int]]:
    moves: List[Dict[str, int]] = []
    for row in range(BOARD_SIZE_4P):
        for col in range(BOARD_SIZE_4P):
            if get_flips_4p(board, row, col, piece, fixed_pieces):
                moves.append({"row": row, "col": col})
    return moves

def count_score_4p(board: List[List[Optional[str]]]) -> Dict[str, int]:
    score = {piece: 0 for piece in PIECES_4P}
    for row in board:
        for cell in row:
            if cell in score:
                score[cell] += 1
    return score