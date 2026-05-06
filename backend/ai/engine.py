import random
import copy
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


# ═══════════════════════════════════════════════════════════════
# CAPA 2: PUNTUACIÓN DEL MEJOR MOVIMIENTO NORMAL
# ═══════════════════════════════════════════════════════════════

def _get_best_normal_move_score_1v1(board, ai_player, fixed_set) -> float:
    """Calcula la puntuación heurística del mejor movimiento normal (1v1)."""
    valid = get_valid_moves(board, ai_player, fixed_set)
    if not valid:
        return float('-inf')
    
    best_val = float('-inf')
    for m in valid:
        new_board = apply_move(board, ai_player, m.row, m.col, fixed_set)
        # Evaluación rápida: posicional + fichas ganadas (sin minimax profundo)
        score_after = count_score(new_board)
        score_before = count_score(board)
        piece_gain = score_after.get(ai_player, 0) - score_before.get(ai_player, 0)
        pos_val = _pos_weight(m.row, m.col, 8)
        val = piece_gain * 3 + pos_val
        if val > best_val:
            best_val = val
    return best_val


def _get_best_normal_move_score_4p(board, ai_player, fixed_set) -> float:
    """Calcula la puntuación heurística del mejor movimiento normal (4P)."""
    valid = get_valid_moves_4p(board, ai_player, fixed_set)
    if not valid:
        return float('-inf')
    
    best_val = float('-inf')
    for m in valid:
        r, c = m["row"], m["col"]
        flips = get_flips_4p(board, r, c, ai_player, fixed_set)
        flip_value = len(flips) * 2
        positional_value = POSITION_WEIGHTS_4P[r][c]
        val = flip_value + positional_value
        if val > best_val:
            best_val = val
    return best_val


# ═══════════════════════════════════════════════════════════════
# CAPA 3: DETECCIÓN DE FINAL DE PARTIDA
# ═══════════════════════════════════════════════════════════════

def _count_empty_cells(board) -> int:
    """Cuenta casillas vacías en el tablero."""
    return sum(1 for row in board for cell in row if cell is None)


def _is_endgame(board, size: int) -> bool:
    """Determina si estamos en final de partida basado en casillas vacías restantes."""
    empty = _count_empty_cells(board)
    # Endgame: menos del 15% del tablero está vacío
    total = size * size
    return empty < total * 0.15


# ═══════════════════════════════════════════════════════════════
# CAPA 1 + 2 + 3: DECISIÓN INTELIGENTE DE USO DE HABILIDADES
# ═══════════════════════════════════════════════════════════════

def get_ai_skill_action(game_state: dict, ai_player: str) -> Optional[dict]:
    """
    Decide si la IA debe usar una habilidad en su turno.
    
    CAPA 1: Condiciones mínimas de rentabilidad por skill (filtro previo).
    CAPA 2: Comparación heurística skill_score vs best_normal_score.
             Solo usa skill si skill_score >= best_normal_score.
    CAPA 3: Gestión de inventario en endgame.
             Si quedan pocos turnos, añade +2 bonus por evitar la penalización
             de -2 pts por skill sin usar. Permite usar incluso lose_turn/give_skill.
    """
    inventory = game_state.get("skills_inventory", {}).get(ai_player, [])
    if not inventory:
        return None

    mode        = game_state.get("mode", "")
    board       = game_state.get("board", [])
    size        = len(board)

    # ── Tasa de error humano: ~15% la IA decide no usar skill y juega normal ──
    # En endgame NO aplica: la IA siempre intenta deshacerse de skills para evitar -2 pts.
    AI_SKILL_MISTAKE_RATE = 0.15
    if not _is_endgame(board, size) and random.random() < AI_SKILL_MISTAKE_RATE:
        return None
    fixed_pieces = game_state.get("fixed_pieces", [])
    fixed_set   = {tuple(p) for p in fixed_pieces}
    skill_inv   = game_state.get("skills_inventory", {})
    skill_tiles = game_state.get("skill_tiles", [])

    is_4p = mode.replace("_skills", "") in ("1v1v1v1", "1vs1vs1vs1")
    is_1v1 = mode.replace("_skills", "") in ("1v1", "1vs1", "vs_ai")

    # Rivales activos
    if is_4p:
        active_pieces = game_state.get("active_pieces", [])
        rivals = [p for p in active_pieces if p != ai_player]
    else:
        rivals = ["white"] if ai_player == "black" else ["black"]

    # Scores actuales
    scores = count_score_4p(board) if is_4p else count_score(board)

    # ── CAPA 2: Puntuación del mejor movimiento normal ──
    if is_4p:
        best_normal_score = _get_best_normal_move_score_4p(board, ai_player, fixed_set)
    else:
        best_normal_score = _get_best_normal_move_score_1v1(board, ai_player, fixed_set)

    # ── CAPA 3: Bonus de endgame para evitar penalización ──
    endgame = _is_endgame(board, size)
    penalty_bonus = 2 if endgame else 0  # Evitar -2 pts por skill sin usar

    # ── Evaluar cada skill del inventario ──
    best_skill_action = None
    best_skill_score = float('-inf')

    for idx, skill in enumerate(inventory):
        action_payload = {"action": "use_skill", "type": skill, "inventory_index": idx}
        skill_score = None  # None = skill no viable en estas condiciones

        # ── GRAVITY ──
        if skill == "gravity":
            score_before = sum(
                _pos_weight(r, c, size) * (1 if board[r][c] == ai_player else -1)
                for r in range(size) for c in range(size)
                if board[r][c] is not None and (board[r][c] == ai_player or board[r][c] in rivals)
            )
            best_dir, best_delta = None, -1
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
                skill_score = best_delta + penalty_bonus

        # ── BOMB ──
        elif skill == "bomb":
            best_r, best_c, best_bomb_score = 0, 0, -1
            for r in range(size):
                for c in range(size):
                    rival_count = sum(
                        1 for br in range(max(0, r-1), min(size, r+2))
                        for bc in range(max(0, c-1), min(size, c+2))
                        if board[br][bc] is not None
                        and board[br][bc] != ai_player
                        and (br, bc) not in fixed_set
                    )
                    if rival_count > best_bomb_score:
                        best_bomb_score, best_r, best_c = rival_count, r, c
            if best_bomb_score >= 2:
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                # Cada ficha convertida vale ~3 puntos heurísticos
                skill_score = best_bomb_score * 3 + penalty_bonus

        # ── FIX_PIECE ──
        elif skill == "fix_piece":
            candidates = [
                (r, c) for r in range(size) for c in range(size)
                if board[r][c] == ai_player and [r, c] not in fixed_pieces
            ]
            if candidates:
                best_r, best_c = max(candidates, key=lambda p: _pos_weight(p[0], p[1], size))
                pw = _pos_weight(best_r, best_c, size)
                if pw > 0:  # Solo fijar fichas en posiciones valiosas
                    action_payload["row"] = best_r
                    action_payload["col"] = best_c
                    # El valor de fijar es proporcional al peso de la casilla
                    skill_score = pw * 0.5 + penalty_bonus

        # ── UNFIX_PIECE ──
        elif skill == "unfix_piece":
            rival_fixed = [
                (r, c) for r, c in fixed_set
                if board[r][c] is not None and board[r][c] != ai_player
            ]
            if rival_fixed:
                best_r, best_c = max(rival_fixed, key=lambda p: _pos_weight(p[0], p[1], size))
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                skill_score = _pos_weight(best_r, best_c, size) * 0.5 + penalty_bonus

        # ── PLACE_FREE ──
        elif skill == "place_free":
            empties = [(r, c) for r in range(size) for c in range(size) if board[r][c] is None]
            if empties:
                best_r, best_c = max(empties, key=lambda p: _pos_weight(p[0], p[1], size))
                pw = _pos_weight(best_r, best_c, size)
                action_payload["row"] = best_r
                action_payload["col"] = best_c
                # Colocar ficha gratis: valor de la casilla + 1 ficha ganada
                skill_score = pw + 3 + penalty_bonus

        # ── SKIP_RIVAL (solo 4P) ──
        elif skill == "skip_rival":
            if is_1v1:
                continue  # No se puede usar en 1v1
            # Saltar al rival siempre tiene valor moderado
            skill_score = 15 + penalty_bonus

        # ── LOSE_TURN ──
        elif skill == "lose_turn":
            # La IA normalmente NUNCA querría perder su turno.
            # Pero en endgame, usarla evita la penalización de -2 pts.
            if endgame:
                skill_score = penalty_bonus  # = 2 (mejor que perder 2 pts)
            else:
                continue  # No usar fuera de endgame

        # ── FLIP_RIVAL ──
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
                # Voltear una ficha rival: ganamos 2 fichas netas (la rival desaparece + la nuestra aparece)
                skill_score = _pos_weight(tr, tc, size) + 6 + penalty_bonus

        # ── SWAP_COLORS ──
        elif skill == "swap_colors":
            my_count = scores.get(ai_player, 0)
            best_target = max(rivals, key=lambda r: scores.get(r, 0), default=None)
            if best_target and scores.get(best_target, 0) > my_count:
                diff = scores.get(best_target, 0) - my_count
                action_payload["target_player"] = best_target
                # Cada ficha de diferencia vale ~3 puntos
                skill_score = diff * 3 + penalty_bonus

        # ── STEAL_SKILL ──
        elif skill == "steal_skill":
            eligible = [(r, skill_inv.get(r, [])) for r in rivals if skill_inv.get(r)]
            if eligible:
                best_target = max(eligible, key=lambda x: len(x[1]))[0]
                action_payload["target_player"] = best_target
                # Robar una habilidad: valor medio estimado
                skill_score = 10 + penalty_bonus

        # ── EXCHANGE_SKILL ──
        elif skill == "exchange_skill":
            eligible = [(r, skill_inv.get(r, [])) for r in rivals if len(skill_inv.get(r, [])) >= 2]
            if eligible:
                action_payload["target_player"] = max(eligible, key=lambda x: len(x[1]))[0]
                skill_score = 5 + penalty_bonus

        # ── GIVE_SKILL ──
        elif skill == "give_skill":
            # La IA normalmente NO regala skills.
            # En endgame, regalar evita la penalización de -2 por la skill regalada
            # Y también consume la propia give_skill (otro -2 evitado).
            if endgame and len(inventory) >= 2:
                # Elegir la skill más "inútil" para regalar (lose_turn preferido)
                worst_to_give = None
                worst_idx = None
                give_priority = ["lose_turn", "give_skill", "exchange_skill", "skip_rival"]
                for gi, gs in enumerate(inventory):
                    if gi == idx:
                        continue  # No podemos dar la propia give_skill (se consume)
                    if gs in give_priority:
                        worst_to_give = gs
                        worst_idx = gi
                        break
                if worst_to_give is None:
                    # Dar cualquier otra
                    for gi, gs in enumerate(inventory):
                        if gi != idx:
                            worst_to_give = gs
                            worst_idx = gi
                            break
                if worst_idx is not None:
                    # Dar al rival más débil (para no beneficiar al fuerte)
                    weakest = min(rivals, key=lambda r: scores.get(r, 0), default=None)
                    if weakest:
                        action_payload["target_player"] = weakest
                        action_payload["given_skill_index"] = worst_idx
                        # Evitamos 2 penalizaciones: la give_skill (consumida) + la skill regalada
                        skill_score = penalty_bonus + 2  # bonus extra por la habilidad regalada
            else:
                continue  # No usar fuera de endgame

        # ── Comparación Capa 2: ¿vale la pena usar esta skill? ──
        if skill_score is not None and skill_score >= best_normal_score:
            if skill_score > best_skill_score:
                best_skill_score = skill_score
                best_skill_action = action_payload

    return best_skill_action
