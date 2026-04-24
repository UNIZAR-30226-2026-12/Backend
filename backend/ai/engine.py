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

def get_best_ai_move(board: Board, player: Player, fixed_pieces: set = None) -> Optional[Coordinate]:
    valid = get_valid_moves(board, player, fixed_pieces)
    if not valid: return None
    best_val, best_move = float('-inf'), valid[0]
    for m in valid:
        new_board = apply_move(board, player, m.row, m.col, fixed_pieces)
        val = minimax(new_board, 3, float('-inf'), float('inf'), False, player)
        if val > best_val:
            best_val, best_move = val, m
    return best_move

def get_best_ai_move_4p(board: Board, player: str, fixed_pieces: set = None) -> Optional[dict]:
    valid = get_valid_moves_4p(board, player, fixed_pieces)
    if not valid: 
        return None
        
    best_val, best_move = float('-inf'), valid[0]
    
    for m in valid:
        r, c = m["row"], m["col"]
        
        # 1. Puntos por cantidad de fichas robadas (cada ficha vale 2 puntos)
        flips = get_flips_4p(board, r, c, player, fixed_pieces)
        flip_value = len(flips) * 2  
        
        # 2. Puntos por el valor estratégico de la casilla en 16x16
        positional_value = POSITION_WEIGHTS_4P[r][c]
        
        # Puntuación final del movimiento
        total_val = flip_value + positional_value
            
        if total_val > best_val:
            best_val = total_val
            best_move = m
            
    return best_move


def get_ai_skill_action(game_state: dict, ai_player: str) -> Optional[dict]:
    """
    Decide si la IA debe usar una habilidad en su turno.
    Devuelve el payload de use_skill o None si no hay habilidad útil disponible.

    La IA nunca usa 'lose_turn' (perdería su turno a propósito).
    Para 'give_skill' solo actúa si tiene más de una habilidad (para no quedarse vacía).
    """
    inventory = game_state.get("skills_inventory", {}).get(ai_player, [])
    if not inventory:
        return None

    mode = game_state.get("mode", "")
    board = game_state.get("board", [])
    size = len(board)
    fixed_pieces = game_state.get("fixed_pieces", [])
    fixed_set = {tuple(p) for p in fixed_pieces}

    # Determinar rivales activos según el modo
    if mode.replace("_skills", "") in ("1v1v1v1", "1vs1vs1vs1"):
        active_pieces = game_state.get("active_pieces", [])
        rivals = [p for p in active_pieces if p != ai_player]
    else:
        rivals = ["white"] if ai_player == "black" else ["black"]

    # Iterar habilidades y devolver el primer payload válido
    for skill in inventory:
        # La IA nunca renuncia a su turno voluntariamente
        if skill == "lose_turn":
            continue

        action_payload = {"action": "use_skill", "type": skill}

        if skill == "gravity":
            action_payload["direction"] = random.choice(["up", "down", "left", "right"])
            return action_payload

        elif skill == "skip_rival":
            # No necesita parámetros extra
            return action_payload

        elif skill == "bomb":
            # Buscar la posición 3x3 con más fichas rivales
            best_r, best_c, best_score = 0, 0, -1
            for r in range(size):
                for c in range(size):
                    rival_count = sum(
                        1 for br in range(max(0, r-1), min(size, r+2))
                        for bc in range(max(0, c-1), min(size, c+2))
                        if board[br][bc] is not None
                        and board[br][bc] != ai_player
                        and (br, bc) not in fixed_set
                    )
                    if rival_count > best_score:
                        best_score = rival_count
                        best_r, best_c = r, c
            if best_score > 0:
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                return action_payload

        elif skill == "fix_piece":
            # Fijar una ficha propia aún no fijada
            for r in range(size):
                for c in range(size):
                    if board[r][c] == ai_player and [r, c] not in fixed_pieces:
                        action_payload["row"] = r
                        action_payload["col"] = c
                        return action_payload

        elif skill == "unfix_piece":
            # Quitar ficha fija rival (beneficia siempre a la IA)
            rival_fixed = [[r, c] for [r, c] in fixed_pieces
                           if board[r][c] is not None and board[r][c] != ai_player]
            if rival_fixed:
                chosen = rival_fixed[0]
                action_payload["row"] = chosen[0]
                action_payload["col"] = chosen[1]
                return action_payload
            # Sin fichas rivales fijadas: pasar a siguiente habilidad
            continue

        elif skill == "place_free":
            # Colocar ficha libre en una casilla vacía
            for r in range(size):
                for c in range(size):
                    if board[r][c] is None:
                        action_payload["row"] = r
                        action_payload["col"] = c
                        return action_payload

        elif skill == "flip_rival":
            # Prioridad: voltear fichas fijas rivales (flip_rival SÍ puede cambiar su color)
            # Si no hay fijas, voltear cualquier ficha rival
            fixed_rival = [(r, c) for r in range(size) for c in range(size)
                           if board[r][c] is not None
                           and board[r][c] != ai_player
                           and (r, c) in fixed_set]
            non_fixed_rival = [(r, c) for r in range(size) for c in range(size)
                               if board[r][c] is not None
                               and board[r][c] != ai_player
                               and (r, c) not in fixed_set]
            target_list = fixed_rival if fixed_rival else non_fixed_rival
            if target_list:
                tr, tc = target_list[0]
                action_payload["row"] = tr
                action_payload["col"] = tc
                return action_payload

        elif skill == "swap_colors":
            if rivals:
                action_payload["target_player"] = random.choice(rivals)
                return action_payload

        elif skill in ("steal_skill", "exchange_skill"):
            skill_inv = game_state.get("skills_inventory", {})
            eligible_rivals = [r for r in rivals if skill_inv.get(r)]
            if eligible_rivals:
                action_payload["target_player"] = random.choice(eligible_rivals)
                return action_payload

        elif skill == "give_skill":
            # Solo regalar si tenemos más de una habilidad
            if len(inventory) > 1 and rivals:
                action_payload["target_player"] = random.choice(rivals)
                return action_payload
            continue

    return None
