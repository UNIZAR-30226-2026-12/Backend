import uuid
from typing import Dict
from rules.schemas import Player
from rules.logic import (
    create_initial_board, is_valid_move, apply_move, 
    get_valid_moves, count_score, resolve_game_state
)
from persistence.database import database

class GameManager:
    def __init__(self):
        self.active_games: Dict[str, dict] = {}

    def create_game(self, creator_name: str, is_private: bool = False, game_id: str = None, mode: str = "1v1") -> str:
        if not game_id:
            game_id = str(uuid.uuid4())
        board = create_initial_board()
        
        self.active_games[game_id] = {
            "game_id": game_id,
            "creator": creator_name,
            "mode": mode,
            "status": "playing" if mode == "vs_ai" else "waiting",
            "board": board,
            "current_player": "black",
            "winner": None,
            "game_over": False,
            "score": count_score(board),
            "valid_moves": [move.dict() for move in get_valid_moves(board, "black")],
            "last_move": None,
            "db_game_id": None,
            "black_player": creator_name,
            "white_player": "IA" if mode == "vs_ai" else None,
            "saved": False 
        }
        return game_id

    def set_game_playing(self, game_id: str, db_game_id: int = None, player1_id: int = None, player2_id: int = None):
        if game_id in self.active_games:
            self.active_games[game_id]["status"] = "playing"
            if db_game_id:
                self.active_games[game_id]["db_game_id"] = db_game_id

    def get_game_state(self, game_id: str) -> dict:
        return self.active_games.get(game_id)

    async def make_move(self, game_id: str, player: Player, row: int, col: int) -> tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game: return False, "Partida no encontrada"
        if game["status"] == "waiting": return False, "Aún no hay rival"
        if game["game_over"]: return False, "La partida ya ha terminado"
        if game["current_player"] != player: return False, "No es tu turno"
        if not is_valid_move(game["board"], player, row, col): return False, "Movimiento inválido"

        game["board"] = apply_move(game["board"], player, row, col)
        game["last_move"] = {"row": row, "col": col}

        next_p = 'white' if player == 'black' else 'black'
        over, winner, current, valid = resolve_game_state(game["board"], next_p)
        
        game["game_over"] = over
        game["winner"] = winner
        game["current_player"] = current
        game["valid_moves"] = [m.dict() for m in valid]
        game["score"] = count_score(game["board"])

        return True, "Movimiento realizado"

    async def surrender_game(self, game_id: str, player: str) -> tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game: return False, "Partida no encontrada"
        if game["status"] == "waiting": return False, "La partida aún no ha empezado"
        if game["game_over"]: return False, "La partida ya ha terminado"

        # El que se rinde pierde, el otro gana
        game["game_over"] = True
        game["winner"] = "white" if player == "black" else "black"
        game["current_player"] = None
        game["valid_moves"] = []

        # Guardamos los resultados inmediatamente
        await self.save_game_results(game_id)

        return True, "Te has rendido"

    async def abandon_game(self, game_id: str, disconnected_username: str) -> tuple[bool, str]:
        game = self.active_games.get(game_id)
        # Solo penalizamos si el juego estaba en curso y no había terminado ya
        if not game or game["game_over"] or game["status"] != "playing":
            return False, "La partida no es susceptible de abandono"

        # Determinamos quién abandonó para darle la victoria al contrario
        if game.get("black_player") == disconnected_username:
            game["winner"] = "white"
        elif game.get("white_player") == disconnected_username:
            game["winner"] = "black"
        else:
            return False, "Jugador no encontrado en esta partida"

        game["game_over"] = True
        game["current_player"] = None
        game["valid_moves"] = []

        # Guardamos los resultados restando el ELO correspondiente
        await self.save_game_results(game_id)

        return True, f"{disconnected_username} abandonó la partida"

    async def save_game_results(self, game_id: str):
        game = self.active_games.get(game_id)
        if not game or game.get("saved"):
            return
            
        game["saved"] = True
        
        black_name = game.get("black_player")
        white_name = game.get("white_player")
        winner_color = game.get("winner")
        mode = game.get("mode", "1v1")
        score = game.get("score")
        
        score_str_black = f"{score['black']}-{score['white']}"
        score_str_white = f"{score['white']}-{score['black']}"
        
        async def get_user_data(username):
            if not username or username == "IA": return None
            return await database.fetch_one("SELECT id, elo FROM users WHERE username = :un", {"un": username})

        black_user = await get_user_data(black_name)
        white_user = await get_user_data(white_name)
        
        black_elo = black_user["elo"] if black_user else 1000
        white_elo = white_user["elo"] if white_user else 1000
        
        expected_black = 1 / (1 + 10 ** ((white_elo - black_elo) / 400))
        expected_white = 1 / (1 + 10 ** ((black_elo - white_elo) / 400))
        
        K = 32
        
        if winner_color == "black":
            s_black, s_white = 1, 0
            res_black, res_white = "Ganada", "Perdida"
        elif winner_color == "white":
            s_black, s_white = 0, 1
            res_black, res_white = "Perdida", "Ganada"
        else:
            s_black, s_white = 0.5, 0.5
            res_black, res_white = "Empate", "Empate"
            
        black_change = int(K * (s_black - expected_black)) if black_user else 0
        white_change = int(K * (s_white - expected_white)) if white_user else 0
        
        # Formateo a String para encajar en el VARCHAR(20) de tu DB
        black_rc_str = f"{black_change:+} RR"
        white_rc_str = f"{white_change:+} RR"
        
        if black_user:
            new_elo = black_elo + black_change
            await database.execute(
                "UPDATE users SET elo = :elo, peak_elo = GREATEST(COALESCE(peak_elo, elo), :elo) WHERE id = :uid",
                {"elo": new_elo, "uid": black_user["id"]}
            )
            await database.execute(
                """INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color) 
                   VALUES (:uid, :opp, :mode, :res, :score, :rc, 'black')""",
                {"uid": black_user["id"], "opp": white_name or "IA", "mode": mode, "res": res_black, "score": score_str_black, "rc": black_rc_str}
            )
            
        if white_user:
            new_elo = white_elo + white_change
            await database.execute(
                "UPDATE users SET elo = :elo, peak_elo = GREATEST(COALESCE(peak_elo, elo), :elo) WHERE id = :uid",
                {"elo": new_elo, "uid": white_user["id"]}
            )
            await database.execute(
                """INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color) 
                   VALUES (:uid, :opp, :mode, :res, :score, :rc, 'white')""",
                {"uid": white_user["id"], "opp": black_name or "IA", "mode": mode, "res": res_white, "score": score_str_white, "rc": white_rc_str}
            )

game_manager = GameManager()