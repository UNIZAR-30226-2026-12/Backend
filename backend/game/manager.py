import uuid
from typing import Dict, List, Optional, Tuple

from persistence.database import database
from rules.logic import (
    apply_move, count_score, create_initial_board, get_valid_moves,
    is_valid_move, resolve_game_state,
    PIECES_4P, TURN_ORDER_4P, create_initial_board_4p, 
    get_flips_4p, get_valid_moves_4p, count_score_4p, is_inside_4p
)

from game.skills import (
    get_random_skill, apply_gravity, apply_bomb, swap_player_colors,
    apply_free_place, apply_flip_rival
)
import random

class GameManager:
    def __init__(self):
        self.active_games: Dict[str, dict] = {}

    def _refresh_paused_state(self, game: dict):
        paused_usernames = list(dict.fromkeys(game.get("paused_usernames", [])))
        participants = set(game.get("participants", []))
        paused_usernames = [u for u in paused_usernames if u in participants]
        game["paused_usernames"] = paused_usernames

        paused_pieces: List[str] = []
        if game.get("mode") == "1v1v1v1":
            piece_by_username = game.get("piece_by_username", {})
            for username in paused_usernames:
                piece = piece_by_username.get(username)
                if piece:
                    paused_pieces.append(piece)
        else:
            black_player = game.get("black_player")
            white_player = game.get("white_player")
            for username in paused_usernames:
                if username == black_player:
                    paused_pieces.append("black")
                elif username == white_player:
                    paused_pieces.append("white")
        game["paused_pieces"] = list(dict.fromkeys(paused_pieces))

    def create_game(self, creator_name: str, is_private: bool = False, game_id: str = None, mode: str = "1v1", invited_name: str = None, participants: Optional[List[str]] = None) -> str:
        if not game_id: game_id = str(uuid.uuid4())

        normalized_mode = "1v1"
        if mode in ("1vs1", "1v1"): normalized_mode = "1v1"
        elif mode in ("1vs1vs1vs1", "1v1v1v1"): normalized_mode = "1v1v1v1"
        elif mode == "vs_ai": normalized_mode = "vs_ai"

        participant_list: List[str] = [name for name in (participants or []) if name]
        if not participant_list:
            participant_list = [creator_name]
            if invited_name: participant_list.append(invited_name)

        if normalized_mode == "1v1v1v1":
            board = create_initial_board_4p()
            username_by_piece: Dict[str, Optional[str]] = {piece: None for piece in PIECES_4P}
            piece_by_username: Dict[str, str] = {}
            for idx, username in enumerate(participant_list[:4]):
                piece = TURN_ORDER_4P[idx]
                username_by_piece[piece] = username
                piece_by_username[username] = piece

            players_ready = {username: False for username in participant_list[:4]}
            skill_tiles = self._generate_skill_tiles(normalized_mode)
            self.active_games[game_id] = {
                "game_id": game_id, "creator": creator_name, "mode": normalized_mode, "status": "waiting",
                "board": board, "current_player": "black", "winner": None, "game_over": False,
                "score": count_score_4p(board), "valid_moves": get_valid_moves_4p(board, "black"),
                "last_move": None, "db_game_id": None, "saved": False, "players_ready": players_ready,
                "participants": participant_list[:4], "participant_count_expected": 4, "turn_order": list(TURN_ORDER_4P),
                "username_by_piece": username_by_piece, "piece_by_username": piece_by_username,
                "active_pieces": [piece for piece, username in username_by_piece.items() if username],
                "abandoned_pieces": [], "final_positions": {},
                "paused_usernames": [], "paused_pieces": [], "invalidated": False, "invalidated_pieces": [],
                "is_private": bool(is_private),
                "black_player": username_by_piece["black"], "white_player": username_by_piece["white"],
                "red_player": username_by_piece["red"], "blue_player": username_by_piece["blue"],
                "skills_inventory": {p: [] for p in PIECES_4P},
                "fixed_pieces": [], # List of [r, c]
                "skill_tiles": skill_tiles, # List of [r, c]
                "skip_next_turn": {p: False for p in PIECES_4P}
            }
            return game_id

        board = create_initial_board()
        black_player = participant_list[0] if participant_list else creator_name
        white_player = "IA" if normalized_mode == "vs_ai" else (participant_list[1] if len(participant_list) > 1 else None)

        players_ready = {black_player: False}
        if white_player and white_player != "IA": players_ready[white_player] = False
        elif white_player == "IA": players_ready["IA"] = True

        skill_tiles = self._generate_skill_tiles(normalized_mode)
        self.active_games[game_id] = {
            "game_id": game_id, "creator": creator_name, "mode": normalized_mode,
            "status": "playing" if normalized_mode == "vs_ai" else "waiting",
            "board": board, "current_player": "black", "winner": None, "game_over": False,
            "score": count_score(board), "valid_moves": [m.dict() for m in get_valid_moves(board, "black")],
            "last_move": None, "db_game_id": None, "black_player": black_player, "white_player": white_player,
            "saved": False, "players_ready": players_ready,
            "participants": [n for n in [black_player, white_player] if n and n != "IA"],
            "participant_count_expected": 1 if normalized_mode == "vs_ai" else 2,
            "paused_usernames": [], "paused_pieces": [], "invalidated": False, "invalidated_pieces": [],
            "is_private": bool(is_private),
            "skills_inventory": {"black": [], "white": []},
            "fixed_pieces": [],
            "skill_tiles": skill_tiles,
            "skip_next_turn": {"black": False, "white": False}
        }
        return game_id

    def set_game_playing(self, game_id: str):
        if game_id in self.active_games:
            self.active_games[game_id]["status"] = "playing"

    def get_game_state(self, game_id: str) -> dict:
        return self.active_games.get(game_id)

    def remove_game(self, game_id: str):
        if game_id in self.active_games:
            del self.active_games[game_id]

    def set_player_ready(self, game_id: str, username: str, ready: bool):
        game = self.active_games.get(game_id)
        if game:
            game.setdefault("players_ready", {})[username] = ready

    def pause_player(self, game_id: str, username: str) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game:
            return False, "Partida no encontrada"
        if game.get("mode") == "vs_ai":
            return False, "No se puede pausar contra la IA"
        if not game.get("is_private"):
            return False, "Solo se pueden pausar partidas con amigos"
        if game.get("status") != "playing" or game.get("game_over"):
            return False, "La partida no esta en curso"
        if username not in game.get("participants", []):
            return False, "No perteneces a la partida"

        paused = game.setdefault("paused_usernames", [])
        if username not in paused:
            paused.append(username)
        self._refresh_paused_state(game)
        return True, "Partida pausada"

    def resume_player(self, game_id: str, username: str) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game:
            return False, "Partida no encontrada"
        paused = game.setdefault("paused_usernames", [])
        if username in paused:
            paused.remove(username)
            self._refresh_paused_state(game)
        return True, "Partida reanudada"

    def are_all_players_ready(self, game_id: str) -> bool:
        game = self.active_games.get(game_id)
        if not game or game.get("status") != "waiting": return False
        participants = game.get("participants", [])
        if len(participants) != game.get("participant_count_expected", 2): return False
        return all(bool(game.get("players_ready", {}).get(u, False)) for u in participants)

    def _generate_skill_tiles(self, mode: str) -> List[List[int]]:
        size = 16 if mode == "1v1v1v1" else 8
        count = 10 if mode == "1v1v1v1" else 5
        tiles = []
        board = create_initial_board_4p() if mode == "1v1v1v1" else create_initial_board()
        empty_tiles = []
        for r in range(size):
            for c in range(size):
                if board[r][c] is None:
                    empty_tiles.append([r, c])
        
        if len(empty_tiles) > count:
            tiles = random.sample(empty_tiles, count)
        else:
            tiles = empty_tiles
        return tiles

    def _handle_landing_on_skill_tile(self, game: dict, player: str, row: int, col: int):
        skill_tiles = game.get("skill_tiles", [])
        if [row, col] in skill_tiles:
            skill_tiles.remove([row, col])
            skill = get_random_skill()
            game["skills_inventory"][player].append(skill)
            return skill
        return None

    # --- HELPERS 4P ---
    def _next_piece_with_moves_4p(self, game: dict, start_piece: str) -> Optional[str]:
        turn_order = game["turn_order"]
        active_pieces = [p for p in turn_order if p in game.get("active_pieces", [])]
        if not active_pieces: return None

        start_idx = turn_order.index(start_piece) if start_piece in turn_order else -1
        for step in range(1, len(turn_order) + 1):
            piece = turn_order[(start_idx + step) % len(turn_order)]
            if piece in active_pieces and get_valid_moves_4p(game["board"], piece):
                return piece
        return None

    def _no_piece_can_move_4p(self, game: dict) -> bool:
        return all(not get_valid_moves_4p(game["board"], p) for p in game.get("active_pieces", []))

    def _finalize_if_finished_4p(self, game: dict):
        active_pieces = game.get("active_pieces", [])
        if len(active_pieces) <= 1 or self._no_piece_can_move_4p(game):
            game["game_over"] = True
            game["status"] = "finished"
            game["current_player"] = None
            game["valid_moves"] = []
            score = count_score_4p(game["board"])
            best = max((score.get(p, 0) for p in active_pieces), default=0)
            leaders = [p for p in active_pieces if score.get(p, 0) == best]
            game["winner"] = leaders[0] if len(leaders) == 1 else "draw"

    async def make_move(self, game_id: str, player: str, row: int, col: int) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game: return False, "Partida no encontrada"
        if game.get("status") != "playing": return False, "La partida no esta en curso"
        if game.get("game_over") or game.get("invalidated"): return False, "La partida ha terminado o es invalida"
        if player in game.get("paused_pieces", []): return False, "Jugador en pausa"

        if game.get("mode") == "1v1v1v1":
            if player not in game.get("active_pieces", []): return False, "Jugador no activo"
            if game["current_player"] != player: return False, "No es tu turno"
            
            fixed_pieces = {tuple(p) for p in game.get("fixed_pieces", [])}
            flips = get_flips_4p(game["board"], row, col, player, fixed_pieces)
            if not flips: return False, "Movimiento invalido"

            game["board"][row][col] = player
            for fr, fc in flips: game["board"][fr][fc] = player
            game["last_move"] = {"row": row, "col": col}
            
            # Check for skill tile
            obtained_skill = self._handle_landing_on_skill_tile(game, player, row, col)
            
            game["score"] = count_score_4p(game["board"])

            self._finalize_if_finished_4p(game)
            if game["game_over"]:
                await self.save_game_results(game_id)
                return True, "Movimiento realizado"

            # Turn progression
            next_piece = self._next_piece_with_moves_4p(game, player)
            if next_piece is None:
                game["game_over"] = True
                game["status"] = "finished"
                game["current_player"] = None
                game["winner"] = "draw"
                await self.save_game_results(game_id)
            else:
                # Handle skip_next_turn
                game["current_player"] = next_piece
                if game["skip_next_turn"].get(next_piece):
                    game["skip_next_turn"][next_piece] = False
                    # Jump again
                    next_next = self._next_piece_with_moves_4p(game, next_piece)
                    if next_next:
                        game["current_player"] = next_next
                        game["valid_moves"] = get_valid_moves_4p(game["board"], next_next, {tuple(p) for p in game.get("fixed_pieces", [])})
                    else:
                        game["game_over"] = True
                        game["status"] = "finished"
                        game["current_player"] = None
                        await self.save_game_results(game_id)
                else:
                    game["valid_moves"] = get_valid_moves_4p(game["board"], next_piece, {tuple(p) for p in game.get("fixed_pieces", [])})
            
            msg = "Movimiento realizado"
            if obtained_skill: msg += f". Has obtenido la habilidad: {obtained_skill}"
            return True, msg

        # --- 1V1 LOGIC ---
        if game["current_player"] != player: return False, "No es tu turno"
        fixed_pieces = {tuple(p) for p in game.get("fixed_pieces", [])}
        if not is_valid_move(game["board"], player, row, col, fixed_pieces): return False, "Movimiento invalido"

        game["board"] = apply_move(game["board"], player, row, col, fixed_pieces)
        game["last_move"] = {"row": row, "col": col}
        
        # Check for skill tile
        obtained_skill = self._handle_landing_on_skill_tile(game, player, row, col)
        
        next_player = "white" if player == "black" else "black"
        
        # Handle skip next turn logic
        if game["skip_next_turn"].get(next_player):
            game["skip_next_turn"][next_player] = False
            next_player = player # Next player is me again? No, in Reversi if opponent skips, it's still my turn? 
            # In 1v1 Reversi, skipping turn means THE OTHER player moves again if they can.
            
        over, winner, current, valid = resolve_game_state(game["board"], next_player)

        game["game_over"] = over
        game["winner"] = winner
        game["current_player"] = current
        game["valid_moves"] = [m.dict() for m in valid]
        game["score"] = count_score(game["board"])

        if over: 
            game["status"] = "finished"
            await self.save_game_results(game_id)
            
        msg = "Movimiento realizado"
        if obtained_skill: msg += f". Has obtenido la habilidad: {obtained_skill}"
        return True, msg

    async def use_skill(self, game_id: str, player: str, skill_data: dict) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game: return False, "Partida no encontrada"
        if game.get("status") != "playing": return False, "La partida no esta en curso"
        if game.get("current_player") != player: return False, "No es tu turno"
        
        skill_type = skill_data.get("type")
        inventory_index = skill_data.get("inventory_index")
        inventory = game.get("skills_inventory", {}).get(player, [])
        
        if skill_type not in inventory:
            return False, "No tienes esa habilidad"
        
        # Validacion del indice si se proporciona
        if inventory_index is not None:
             if inventory_index < 0 or inventory_index >= len(inventory) or inventory[inventory_index] != skill_type:
                 # fallback a la primera ocurrencia si el indice no coincide (por si acaso)
                 try:
                     inventory_index = inventory.index(skill_type)
                 except ValueError:
                     return False, "Habilidad no encontrada en el inventario"
        else:
            # Si no hay indice, buscamos la primera
            try:
                inventory_index = inventory.index(skill_type)
            except ValueError:
                return False, "Habilidad no encontrada en el inventario"
            
        success = False
        msg = ""
        fixed_set = {tuple(p) for p in game.get("fixed_pieces", [])}

        # --- BRANCH LOGIC FOR EACH SKILL ---
        if skill_type == "gravity":
            direction = skill_data.get("direction")
            if not direction:
                return False, "Direccion de gravedad no especificada"
            
            game["board"] = apply_gravity(game["board"], direction, fixed_set)
            success, msg = True, f"Gravedad aplicada hacia {direction}"

        elif skill_type == "bomb":
            r, c = skill_data.get("row"), skill_data.get("col")
            if r is None or c is None: return False, "Coordenadas faltantes"
            game["board"] = apply_bomb(game["board"], r, c, player)
            success, msg = True, "Bomba 3x3 detonada"

        elif skill_type == "fix_piece":
            r, c = skill_data.get("row"), skill_data.get("col")
            if r is None or c is None: return False, "Coordenadas faltantes"
            if game["board"][r][c] != player: return False, "Esa ficha no es tuya"
            if [r, c] in game.get("fixed_pieces", []): return False, "La ficha ya es fija"
            game["fixed_pieces"].append([r, c])
            success, msg = True, "Ficha fijada correctamente"

        elif skill_type == "unfix_piece":
            r, c = skill_data.get("row"), skill_data.get("col")
            if [r, c] not in game.get("fixed_pieces", []): return False, "No es una ficha fija"
            game["fixed_pieces"].remove([r, c])
            success, msg = True, "Ficha liberada correctamente"

        elif skill_type == "place_free":
            r, c = skill_data.get("row"), skill_data.get("col")
            if game["board"][r][c] is not None: return False, "Casilla ocupada"
            game["board"] = apply_free_place(game["board"], r, c, player)
            success, msg = True, "Ficha libre colocada"

        elif skill_type == "skip_rival":
            mode = game.get("mode")
            rival = None
            if mode == "1v1":
                rival = "white" if player == "black" else "black"
            else:
                turn_order = game["turn_order"]
                active = game["active_pieces"]
                idx = turn_order.index(player)
                for step in range(1, 4):
                    p_candidate = turn_order[(idx + step) % 4]
                    if p_candidate in active:
                        rival = p_candidate
                        break
            if rival:
                game["skip_next_turn"][rival] = True
                success, msg = True, f"Turno de {rival} saltado"
            else: return False, "No hay rival al que saltar"

        elif skill_type == "lose_turn":
            success, msg = True, "Has decidido perder tu turno"

        elif skill_type == "flip_rival":
            r, c = skill_data.get("row"), skill_data.get("col")
            if game["board"][r][c] is None or game["board"][r][c] == player: return False, "Casilla no valida"
            game["board"] = apply_flip_rival(game["board"], r, c, player, fixed_set)
            success, msg = True, "Ficha rival volteada"

        elif skill_type == "swap_colors":
            target = skill_data.get("target_player")
            if not target or target == player: return False, "Objetivo no valido"
            game["board"] = swap_player_colors(game["board"], player, target)
            success, msg = True, f"Colores intercambiados con {target}"

        elif skill_type == "steal_skill":
            target = skill_data.get("target_player")
            if not target or target == player: return False, "Objetivo no valido"
            target_inv = game["skills_inventory"].get(target, [])
            if not target_inv: return False, "El rival no tiene habilidades"
            skill = target_inv.pop(random.randint(0, len(target_inv)-1))
            game["skills_inventory"][player].append(skill)
            success, msg = True, f"Has robado la habilidad {skill} a {target}"

        elif skill_type == "exchange_skill":
            target = skill_data.get("target_player")
            if not target or target == player: return False, "Objetivo no valido"
            target_inv = game["skills_inventory"].get(target, [])
            player_inv = game["skills_inventory"][player]
            
            if not target_inv: return False, "El rival no tiene habilidades"
            
            # Buscamos candidatos que no sean la propia habilidad exchange_skill que estamos usando
            candidates = [i for i, s in enumerate(player_inv) if i != inventory_index]
            if not candidates:
                return False, "No tienes otra habilidad para intercambiar"
                
            idx_p = random.choice(candidates)
            idx_t = random.randint(0, len(target_inv)-1)
            
            # Guardamos para el mensaje
            s_p = player_inv[idx_p]
            s_t = target_inv[idx_t]
            
            # Intercambiamos sin usar pop todavia para no alterar indices
            player_inv[idx_p] = s_t
            target_inv[idx_t] = s_p
            
            success, msg = True, f"Intercambiada {s_p} por {s_t} con {target}"

        elif skill_type == "give_skill":
            target = skill_data.get("target_player")
            if not target or target == player: return False, "Objetivo no valido"
            
            # El inventario actual incluye la propia habilidad 'give_skill' que se esta usando
            player_inv = game["skills_inventory"][player]
            
            # Buscamos habilidades candidatas (que no sean la que estamos usando para regalar)
            # Nota: si tiene dos 'give_skill', podria regalar una.
            candidates = [s for i, s in enumerate(player_inv) if i != inventory_index]
            
            if not candidates:
                return False, "No tienes otra habilidad para regalar"
            
            # Elegimos una de las candidatas para regalar
            skill_to_gift = random.choice(candidates)
            
            # La quitamos del inventario del jugador (buscando por indice para evitar problemas si hay duplicadas)
            gifted_idx = -1
            for i, s in enumerate(player_inv):
                if i != inventory_index and s == skill_to_gift:
                    gifted_idx = i
                    break
            
            if gifted_idx != -1:
                player_inv.pop(gifted_idx)
                # AJUSTE DE INDICE: Si el que regalamos estaba antes en la lista, el nuestro baja una posicion
                if gifted_idx < inventory_index:
                    inventory_index -= 1
                    
                game["skills_inventory"][target].append(skill_to_gift)
                success, msg = True, f"Has regalado la habilidad {skill_to_gift} a {target}"
            else:
                return False, "Error al procesar el regalo"

        if success:
            inventory.pop(inventory_index) # Consumo final por indice
            # --- TURN CONCESSION ---
            mode = game.get("mode")
            if mode == "1v1v1v1":
                game["score"] = count_score_4p(game["board"])
                self._finalize_if_finished_4p(game)
                if not game["game_over"]:
                    next_p = self._next_piece_with_moves_4p(game, player)
                    if next_p:
                        if game["skip_next_turn"].get(next_p):
                            game["skip_next_turn"][next_p] = False
                            next_p = self._next_piece_with_moves_4p(game, next_p)
                        if next_p:
                            game["current_player"] = next_p
                            game["valid_moves"] = get_valid_moves_4p(game["board"], next_p, {tuple(p) for p in game.get("fixed_pieces", [])})
                        else: game["game_over"] = True
                    else: game["game_over"] = True
                if game.get("game_over"): await self.save_game_results(game_id)
            else:
                game["score"] = count_score(game["board"])
                next_p = "white" if player == "black" else "black"
                if game["skip_next_turn"].get(next_p):
                    game["skip_next_turn"][next_p] = False
                    next_p = player
                over, winner, curr, valid = resolve_game_state(game["board"], next_p)
                game["game_over"] = over
                game["winner"] = winner
                game["current_player"] = curr
                game["valid_moves"] = [m.dict() for m in valid]
                if over:
                    game["status"] = "finished"
                    await self.save_game_results(game_id)
            return True, msg
        
        return False, "Error al procesar habilidad"

    async def surrender_game(self, game_id: str, player: str) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game or game["game_over"]: return False, "No es posible rendirse"

        if game.get("mode") == "1v1v1v1":
            username = game.get("username_by_piece", {}).get(player, player)
            return await self.abandon_game(game_id, username)

        game["game_over"] = True
        game["winner"] = "white" if player == "black" else "black"
        game["current_player"] = None
        game["status"] = "finished"
        await self.save_game_results(game_id)
        return True, "Te has rendido"

    async def abandon_game(self, game_id: str, disconnected_username: str) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game or game["game_over"] or game["status"] != "playing": return False, "Abandono ignorado"

        mode = game.get("mode")
        paused_usernames = game.get("paused_usernames", [])
        disconnected_was_paused = disconnected_username in paused_usernames
        if paused_usernames and not disconnected_was_paused:
            if mode == "1v1":
                game["invalidated"] = True
                game["game_over"] = True
                game["winner"] = None
                game["current_player"] = None
                game["status"] = "finished"
                game["valid_moves"] = []
                game["paused_usernames"] = []
                game["paused_pieces"] = []
                return True, f"{disconnected_username} abandono y la partida ha sido invalidada sin cambios de RR"

            if mode == "1v1v1v1":
                piece = game.get("piece_by_username", {}).get(disconnected_username)
                if not piece or piece not in game.get("active_pieces", []):
                    return False, "Jugador inactivo"

                game["active_pieces"].remove(piece)
                abandoned_pieces = game.setdefault("abandoned_pieces", [])
                if piece not in abandoned_pieces:
                    abandoned_pieces.append(piece)
                invalidated_pieces = game.setdefault("invalidated_pieces", [])
                if piece not in invalidated_pieces:
                    invalidated_pieces.append(piece)
                game.setdefault("final_positions", {})[piece] = 4
                game["score"] = count_score_4p(game["board"])

                if len(game.get("active_pieces", [])) < 2:
                    game["invalidated"] = True
                    game["game_over"] = True
                    game["winner"] = None
                    game["current_player"] = None
                    game["status"] = "finished"
                    game["valid_moves"] = []
                    game["paused_usernames"] = []
                    game["paused_pieces"] = []
                    return True, f"{disconnected_username} abandono y la partida ha sido invalidada sin cambios de RR"

                self._refresh_paused_state(game)
                self._finalize_if_finished_4p(game)

                if game["game_over"]:
                    await self.save_game_results(game_id)
                    return True, f"{disconnected_username} abandono y la partida finalizo sin cambios de RR para ese jugador"

                if game.get("current_player") == piece:
                    next_piece = self._next_piece_with_moves_4p(game, piece)
                    if next_piece is None:
                        game["game_over"] = True
                        game["status"] = "finished"
                        game["current_player"] = None
                        game["winner"] = "draw"
                        await self.save_game_results(game_id)
                    else:
                        game["current_player"] = next_piece
                        game["valid_moves"] = get_valid_moves_4p(game["board"], next_piece)
                return True, f"{disconnected_username} abandono la partida pausada sin cambios de RR para ese jugador"

        if mode == "1v1v1v1":
            piece = game.get("piece_by_username", {}).get(disconnected_username)
            if not piece or piece not in game.get("active_pieces", []): return False, "Jugador inactivo"
            game["active_pieces"].remove(piece)
            game.setdefault("abandoned_pieces", []).append(piece)
            game.setdefault("final_positions", {})[piece] = 4
            game["score"] = count_score_4p(game["board"])
            game.get("paused_usernames", [])[:] = [u for u in game.get("paused_usernames", []) if u != disconnected_username]
            self._refresh_paused_state(game)
            self._finalize_if_finished_4p(game)
            if game["game_over"]:
                await self.save_game_results(game_id)
                return True, "Abandono procesado"
            
            if game.get("current_player") == piece:
                next_piece = self._next_piece_with_moves_4p(game, piece)
                if next_piece is None:
                    game["game_over"] = True
                    game["status"] = "finished"
                    game["current_player"] = None
                    game["winner"] = "draw"
                    await self.save_game_results(game_id)
                else:
                    game["current_player"] = next_piece
                    game["valid_moves"] = get_valid_moves_4p(game["board"], next_piece)
            return True, f"{disconnected_username} abandono"

        if game.get("black_player") == disconnected_username: game["winner"] = "white"
        elif game.get("white_player") == disconnected_username: game["winner"] = "black"
        else: return False, "Jugador no encontrado"

        game.get("paused_usernames", [])[:] = [u for u in game.get("paused_usernames", []) if u != disconnected_username]
        self._refresh_paused_state(game)
        game["game_over"] = True
        game["current_player"] = None
        game["status"] = "finished"
        await self.save_game_results(game_id)
        return True, f"{disconnected_username} abandono"

    async def _save_game_results_1v1(self, game: dict):
        black_name = game.get("black_player")
        white_name = game.get("white_player")
        
        # Penalties logic
        score = count_score(game["board"])
        inv = game.get("skills_inventory", {})
        b_penalty = len(inv.get("black", [])) * 2
        w_penalty = len(inv.get("white", [])) * 2
        
        score["black"] = max(0, score["black"] - b_penalty)
        score["white"] = max(0, score["white"] - w_penalty)
        game["score"] = score
        
        # Decide winner based on penalized score
        if score["black"] > score["white"]: winner_color = "black"
        elif score["white"] > score["black"]: winner_color = "white"
        else: winner_color = "draw"
        
        s_b = f"{score['black']}-{score['white']}"
        s_w = f"{score['white']}-{score['black']}"

        async def get_usr(un): return await database.fetch_one("SELECT id, elo FROM users WHERE username = :un", {"un": un}) if un and un != "IA" else None
        b_usr, w_usr = await get_usr(black_name), await get_usr(white_name)
        
        b_ch = 30 if winner_color == "black" else (-30 if winner_color == "white" else 0)
        w_ch = 30 if winner_color == "white" else (-30 if winner_color == "black" else 0)
        res_b = "Ganada" if winner_color == "black" else ("Perdida" if winner_color == "white" else "Empate")
        res_w = "Ganada" if winner_color == "white" else ("Perdida" if winner_color == "black" else "Empate")

        async def update_db(usr, ch, res, sc, col, opp):
            if usr:
                await database.execute("UPDATE users SET elo=elo+:ch, peak_elo=GREATEST(COALESCE(peak_elo, elo), elo+:ch) WHERE id=:id", {"ch": ch, "id": usr["id"]})
                await database.execute("INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color) VALUES (:uid, :opp, :m, :res, :sc, :rc, :col)",
                    {"uid": usr["id"], "opp": opp or "IA", "m": game.get("mode", "1v1"), "res": res, "sc": sc, "rc": f"{ch:+} RR", "col": col})

        await update_db(b_usr, b_ch, res_b, s_b, 'black', white_name)
        await update_db(w_usr, w_ch, res_w, s_w, 'white', black_name)

    def _compute_positions_4p(self, game: dict) -> Dict[str, int]:
        invalidated_pieces = set(game.get("invalidated_pieces", []))
        valid_pieces = [
            p for p in PIECES_4P
            if game.get("username_by_piece", {}).get(p) and p not in invalidated_pieces
        ]
        if not valid_pieces:
            return {}

        # Penalties logic
        score = count_score_4p(game["board"])
        inv = game.get("skills_inventory", {})
        for p in PIECES_4P:
            penalty = len(inv.get(p, [])) * 2
            score[p] = max(0, score[p] - penalty)
        game["score"] = score

        positions = {
            piece: rank
            for piece, rank in dict(game.get("final_positions", {})).items()
            if piece in valid_pieces
        }
        remaining = [p for p in valid_pieces if p not in positions]
        
        score_groups = {}
        for p in remaining:
            s = score.get(p, 0)
            score_groups.setdefault(s, []).append(p)
            
        available_ranks = [i for i in range(1, len(valid_pieces) + 1) if i not in positions.values()]
        sorted_scores = sorted(score_groups.keys(), reverse=True)
        
        for s in sorted_scores:
            if not available_ranks: break
            rank = available_ranks[0] # Todos los empatados reciben este rango
            for p in score_groups[s]:
                positions[p] = rank
                available_ranks.pop(0) # Se consume un puesto por cada jugador empatado
                
        return positions

    async def _save_game_results_4p(self, game: dict):
        positions = self._compute_positions_4p(game)
        rr_map = {1: 50, 2: 25, 3: 0, 4: -25}
        score = count_score_4p(game["board"])
        invalidated_pieces = set(game.get("invalidated_pieces", []))
        valid_usernames = [
            game.get("username_by_piece", {}).get(piece)
            for piece in PIECES_4P
            if game.get("username_by_piece", {}).get(piece) and piece not in invalidated_pieces
        ]
        parts = [u for u in valid_usernames if u]
        
        for piece in PIECES_4P:
            un = game.get("username_by_piece", {}).get(piece)
            if not un or piece in invalidated_pieces: continue
            row = await database.fetch_one("SELECT id, elo FROM users WHERE username = :un", {"un": un})
            if not row: continue
            pos = positions.get(piece, 4)
            delta = rr_map.get(pos, -25)
            opps = ", ".join([p for p in parts if p != un])
            await database.execute("UPDATE users SET elo = GREATEST(0, elo+:d), peak_elo = GREATEST(COALESCE(peak_elo, elo), GREATEST(0, elo+:d)) WHERE id = :uid", {"d": delta, "uid": row["id"]})
            await database.execute("INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color) VALUES (:uid, :opp, '1vs1vs1vs1', :res, :sc, :rc, :col)",
                {"uid": row["id"], "opp": opps or "N/A", "res": f"{pos}º", "sc": f"{pos}º puesto · {score.get(piece, 0)} pts", "rc": f"{delta:+} RR", "col": piece})

    async def save_game_results(self, game_id: str):
        game = self.active_games.get(game_id)
        if game and game.get("invalidated"):
            game["saved"] = True
            return
        if game and not game.get("saved"):
            game["saved"] = True
            if game.get("mode") == "1v1v1v1": await self._save_game_results_4p(game)
            else: await self._save_game_results_1v1(game)

game_manager = GameManager()
