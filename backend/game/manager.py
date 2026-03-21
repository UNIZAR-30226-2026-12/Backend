import uuid
from typing import Dict
from rules.schemas import Player
from rules.logic import (
    create_initial_board, is_valid_move, apply_move, 
    get_valid_moves, count_score, resolve_game_state
)

class GameManager:
    def __init__(self):
        self.active_games: Dict[str, dict] = {}

    def create_game(self, creator_name: str, is_private: bool = False, game_id: str = None) -> str:
        if not game_id:
            game_id = str(uuid.uuid4())
        board = create_initial_board()
        
        self.active_games[game_id] = {
            "game_id": game_id,
            "creator": creator_name,
            "status": "waiting",
            "board": board,
            "current_player": "black",
            "winner": None,
            "game_over": False,
            "score": count_score(board),
            "valid_moves": [move.dict() for move in get_valid_moves(board, "black")],
            "last_move": None,
            "db_game_id": None
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

game_manager = GameManager()