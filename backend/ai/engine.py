import random
from typing import Optional
from rules.schemas import Player, Board, Coordinate, BOARD_SIZE
from rules.logic import get_valid_moves, apply_move, count_score, get_valid_moves_4p, count_score_4p, get_flips_4p
from skills.effects import apply_gravity

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

def _pos_weight(r: int, c: int, size: int) -> int:
    """Peso posicional de la casilla según el tamaño del tablero. Reutilizado por fix_piece, flip_rival, place_free y unfix_piece."""
    W = POSITION_WEIGHTS_4P if size == 16 else POSITION_WEIGHTS
    return W[r][c]

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
    Capa 1: condiciones mínimas de rentabilidad por skill.
    - gravity   : simula las 4 direcciones, elige la de mejor ganancia posicional neta (≥0).
    - bomb      : solo si hay ≥2 fichas rivales no fijas en el radio 3x3.
    - fix_piece : ficha propia con mayor peso posicional (esquina > borde > centro).
    - unfix     : ficha fija rival con mayor peso posicional.
    - place_free: casilla vacía con mayor peso posicional.
    - flip_rival: fija rival > no-fija rival, ambas por mayor peso posicional.
    - swap      : solo si al menos un rival tiene más fichas que la IA; elige el más fuerte.
    - steal     : rival con más skills en inventario.
    - skip      : siempre (no puede elegir a quién en el protocolo actual).
    - exchange  : solo si el rival tiene ≥2 skills.
    - give/lose : nunca (la IA no se sabotea ni regala skills activamente).
    Bug fix: usa enumerate para enviar el inventory_index correcto al manager.
    """
    inventory = game_state.get("skills_inventory", {}).get(ai_player, [])
    if not inventory:
        return None

    # ── Tasa de error humano: ~15% la IA decide no usar skill y juega normal ──
    AI_SKILL_MISTAKE_RATE = 0.15
    if random.random() < AI_SKILL_MISTAKE_RATE:
        return None

    mode        = game_state.get("mode", "")
    board       = game_state.get("board", [])
    size        = len(board)
    fixed_pieces = game_state.get("fixed_pieces", [])
    fixed_set   = {tuple(p) for p in fixed_pieces}
    skill_inv   = game_state.get("skills_inventory", {})
    skill_tiles = game_state.get("skill_tiles", [])

    # Rivales activos
    if mode.replace("_skills", "") in ("1v1v1v1", "1vs1vs1vs1"):
        active_pieces = game_state.get("active_pieces", [])
        rivals = [p for p in active_pieces if p != ai_player]
    else:
        rivals = ["white"] if ai_player == "black" else ["black"]

    # Scores de fichas actuales (reutilizados por swap y skip)
    scores = count_score(board)

    for idx, skill in enumerate(inventory):
        # La IA nunca se sabotea ni regala skills activamente
        if skill in ("lose_turn", "give_skill"):
            continue

        action_payload = {"action": "use_skill", "type": skill, "inventory_index": idx}

        # ── GRAVITY: simular las 4 dirs, elegir la de mejor ganancia posicional ──
        if skill == "gravity":
            score_before = sum(
                _pos_weight(r, c, size) * (1 if board[r][c] == ai_player else -1)
                for r in range(size) for c in range(size)
                if board[r][c] is not None and (board[r][c] == ai_player or board[r][c] in rivals)
            )
            best_dir, best_delta = None, -1  # exige al menos delta > -1 (≥0 neto)
            for direction in ("up", "down", "left", "right"):
                sim_board, _ = apply_gravity(board, direction, fixed_set, skill_tiles)
                score_after = sum(
                    _pos_weight(r, c, size) * (1 if sim_board[r][c] == ai_player else -1)
                    for r in range(size) for c in range(size)
                    if sim_board[r][c] is not None and (sim_board[r][c] == ai_player or sim_board[r][c] in rivals)
                )
                delta = score_after - score_before
                if delta > best_delta:
                    best_delta, best_dir = delta, direction
            if best_dir and best_delta >= 0:
                action_payload["direction"] = best_dir
                return action_payload
            continue

        # ── BOMB: solo si ≥2 fichas rivales no fijas en el radio 3x3 ──
        elif skill == "bomb":
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
                        best_score, best_r, best_c = rival_count, r, c
            if best_score >= 2:
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                return action_payload
            continue

        # ── FIX_PIECE: ficha propia con mayor peso posicional ──
        elif skill == "fix_piece":
            candidates = [
                (r, c) for r in range(size) for c in range(size)
                if board[r][c] == ai_player and [r, c] not in fixed_pieces
            ]
            if candidates:
                best_r, best_c = max(candidates, key=lambda p: _pos_weight(p[0], p[1], size))
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                return action_payload
            continue

        # ── UNFIX_PIECE: ficha fija rival con mayor peso posicional ──
        elif skill == "unfix_piece":
            rival_fixed = [
                (r, c) for r, c in fixed_set
                if board[r][c] is not None and board[r][c] != ai_player
            ]
            if rival_fixed:
                best_r, best_c = max(rival_fixed, key=lambda p: _pos_weight(p[0], p[1], size))
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                return action_payload
            continue

        # ── PLACE_FREE: casilla vacía con mayor peso posicional ──
        elif skill == "place_free":
            empties = [(r, c) for r in range(size) for c in range(size) if board[r][c] is None]
            if empties:
                best_r, best_c = max(empties, key=lambda p: _pos_weight(p[0], p[1], size))
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                return action_payload
            continue

        # ── FLIP_RIVAL: fija rival > no-fija rival; dentro de cada grupo, la de mayor peso ──
        elif skill == "flip_rival":
            fixed_rival = [
                (r, c) for r in range(size) for c in range(size)
                if board[r][c] is not None and board[r][c] != ai_player and (r, c) in fixed_set
            ]
            non_fixed_rival = [
                (r, c) for r in range(size) for c in range(size)
                if board[r][c] is not None and board[r][c] != ai_player and (r, c) not in fixed_set
            ]
            pool = fixed_rival if fixed_rival else non_fixed_rival
            if pool:
                tr, tc = max(pool, key=lambda p: _pos_weight(p[0], p[1], size))
                action_payload["row"] = tr
                action_payload["col"] = tc
                return action_payload
            continue

        # ── SWAP_COLORS: solo si algún rival tiene más fichas que la IA ──
        elif skill == "swap_colors":
            my_count = scores.get(ai_player, 0)
            best_target = max(rivals, key=lambda r: scores.get(r, 0), default=None)
            if best_target and scores.get(best_target, 0) > my_count:
                action_payload["target_player"] = best_target
                return action_payload
            continue

        # ── STEAL_SKILL: al rival con más habilidades en inventario ──
        elif skill == "steal_skill":
            eligible = [(r, skill_inv.get(r, [])) for r in rivals if skill_inv.get(r)]
            if eligible:
                action_payload["target_player"] = max(eligible, key=lambda x: len(x[1]))[0]
                return action_payload
            continue

        # ── SKIP_RIVAL (4P): siempre disponible cuando se tiene, sin parámetros extra ──
        elif skill == "skip_rival":
            return action_payload

        # ── EXCHANGE_SKILL: solo si el rival tiene ≥2 skills (ganancia esperada positiva) ──
        elif skill == "exchange_skill":
            eligible = [(r, skill_inv.get(r, [])) for r in rivals if len(skill_inv.get(r, [])) >= 2]
            if eligible:
                action_payload["target_player"] = max(eligible, key=lambda x: len(x[1]))[0]
                return action_payload
            continue

    return None
