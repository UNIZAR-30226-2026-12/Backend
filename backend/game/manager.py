import uuid
from typing import Dict, List, Optional, Tuple

from persistence.database import database
from rules.logic import (
    apply_move, count_score, create_initial_board, get_valid_moves,
    is_valid_move, resolve_game_state,
    PIECES_4P, TURN_ORDER_4P, create_initial_board_4p, 
    get_flips_4p, get_valid_moves_4p, count_score_4p, is_inside_4p
)

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
            }
            return game_id

        board = create_initial_board()
        black_player = participant_list[0] if participant_list else creator_name
        white_player = "IA" if normalized_mode == "vs_ai" else (participant_list[1] if len(participant_list) > 1 else None)

        players_ready = {black_player: False}
        if white_player and white_player != "IA": players_ready[white_player] = False
        elif white_player == "IA": players_ready["IA"] = True

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
        if game["status"] == "waiting": return False, "La partida aun no ha empezado"
        if game["game_over"]: return False, "La partida ya ha terminado"
        if player in game.get("paused_pieces", []): return False, "Jugador en pausa"

        if game.get("mode") == "1v1v1v1":
            if player not in game.get("active_pieces", []): return False, "Jugador no activo"
            if game["current_player"] != player: return False, "No es tu turno"
            
            flips = get_flips_4p(game["board"], row, col, player)
            if not flips: return False, "Movimiento invalido"

            game["board"][row][col] = player
            for fr, fc in flips: game["board"][fr][fc] = player
            game["last_move"] = {"row": row, "col": col}
            game["score"] = count_score_4p(game["board"])

            self._finalize_if_finished_4p(game)
            if game["game_over"]:
                await self.save_game_results(game_id)
                return True, "Movimiento realizado"

            next_piece = self._next_piece_with_moves_4p(game, player)
            if next_piece is None:
                game["game_over"] = True
                game["status"] = "finished"
                game["current_player"] = None
                game["winner"] = "draw"
                await self.save_game_results(game_id)
            else:
                game["current_player"] = next_piece
                game["valid_moves"] = get_valid_moves_4p(game["board"], next_piece)
            return True, "Movimiento realizado"

        # --- 1V1 LOGIC ---
        if game["current_player"] != player: return False, "No es tu turno"
        if not is_valid_move(game["board"], player, row, col): return False, "Movimiento invalido"

        game["board"] = apply_move(game["board"], player, row, col)
        game["last_move"] = {"row": row, "col": col}
        next_player = "white" if player == "black" else "black"
        over, winner, current, valid = resolve_game_state(game["board"], next_player)

        game["game_over"] = over
        game["winner"] = winner
        game["current_player"] = current
        game["valid_moves"] = [m.dict() for m in valid]
        game["score"] = count_score(game["board"])

        if over: game["status"] = "finished"
        return True, "Movimiento realizado"

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
        # Mismo código que ya tenías para 1v1
        black_name = game.get("black_player")
        white_name = game.get("white_player")
        winner_color = game.get("winner")
        score = game.get("score", {"black": 0, "white": 0})
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

        score = count_score_4p(game["board"])
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
