from typing import Optional
from rules.schemas import Player, Board, Coordinate, BOARD_SIZE
from rules.logic import get_valid_moves, apply_move, count_score

POSITION_WEIGHTS = [
    [100, -20, 10, 5, 5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [10, -2, -1, -1, -1, -1, -2, 10],
    [5, -2, -1, -1, -1, -1, -2, 5],
    [5, -2, -1, -1, -1, -1, -2, 5],
    [10, -2, -1, -1, -1, -1, -2, 10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10, 5, 5, 10, -20, 100]
]

def evaluate_board(board: Board, player: Player) -> int:
    opponent = 'white' if player == 'black' else 'black'
    score = 0
    counts = count_score(board)
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == player: score += POSITION_WEIGHTS[r][c]
            elif board[r][c] == opponent: score -= POSITION_WEIGHTS[r][c]
    
    my_moves = len(get_valid_moves(board, player))
    op_moves = len(get_valid_moves(board, opponent))
    score += (my_moves - op_moves) * 15 # Priorizar movilidad
    return score

def minimax(board: Board, depth: int, alpha: float, beta: float, maximizing: bool, ai_player: Player) -> float:
    human_player = 'black' if ai_player == 'white' else 'white'
    current_p = ai_player if maximizing else human_player
    
    moves = get_valid_moves(board, current_p)
    
    if depth == 0 or not moves:
        return evaluate_board(board, ai_player)
    
    if maximizing:
        max_eval = float('-inf')
        for m in moves:
            new_board = apply_move(board, ai_player, m.row, m.col)
            eval_val = minimax(new_board, depth - 1, alpha, beta, False, ai_player)
            max_eval = max(max_eval, eval_val)
            alpha = max(alpha, eval_val)
            if beta <= alpha: break
        return max_eval
    else:
        min_eval = float('inf')
        for m in moves:
            new_board = apply_move(board, human_player, m.row, m.col)
            eval_val = minimax(new_board, depth - 1, alpha, beta, True, ai_player)
            min_eval = min(min_eval, eval_val)
            beta = min(beta, eval_val)
            if beta <= alpha: break
        return min_eval

def get_best_ai_move(board: Board, player: Player) -> Optional[Coordinate]:
    valid = get_valid_moves(board, player)
    if not valid: return None
    best_val, best_move = float('-inf'), valid[0]
    for m in valid:
        new_board = apply_move(board, player, m.row, m.col)
        val = minimax(new_board, 3, float('-inf'), float('inf'), False, player)
        if val > best_val:
            best_val, best_move = val, m
    return best_move