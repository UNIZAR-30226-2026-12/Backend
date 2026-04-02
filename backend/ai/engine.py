from typing import Optional
from rules.schemas import Player, Board, Coordinate, BOARD_SIZE
from rules.logic import get_valid_moves, apply_move, count_score
from typing import Optional
from rules.schemas import Player, Board, Coordinate, BOARD_SIZE
from rules.logic import get_valid_moves, apply_move, count_score, get_valid_moves_4p, count_score_4p, get_flips_4p

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

POSITION_WEIGHTS_4P = [
    [ 500, -100,  50,  50,  50,  50,  50,  50,  50,  50,  50,  50,  50,  50, -100,  500],
    [-100, -200, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -200, -100],
    [  50,  -10,  10,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,  10,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,   5,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   5,  -10,   50],
    [  50,  -10,  10,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,  10,  -10,   50],
    [-100, -200, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -200, -100],
    [ 500, -100,  50,  50,  50,  50,  50,  50,  50,  50,  50,  50,  50,  50, -100,  500]
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

def get_best_ai_move_4p(board: Board, player: str) -> Optional[dict]:
    """ 
    Heurística Greedy usando matriz de pesos estática para el tablero 16x16.
    Combina el valor posicional de la casilla con la cantidad de fichas capturadas.
    """
    valid = get_valid_moves_4p(board, player)
    if not valid: 
        return None
        
    best_val, best_move = float('-inf'), valid[0]
    
    for m in valid:
        r, c = m["row"], m["col"]
        
        # 1. Puntos por cantidad de fichas robadas (cada ficha vale 2 puntos)
        flips = get_flips_4p(board, r, c, player)
        flip_value = len(flips) * 2  
        
        # 2. Puntos por el valor estratégico de la casilla en 16x16
        positional_value = POSITION_WEIGHTS_4P[r][c]
        
        # Puntuación final del movimiento
        total_val = flip_value + positional_value
            
        if total_val > best_val:
            best_val = total_val
            best_move = m
            
    return best_move