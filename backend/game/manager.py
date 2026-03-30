import uuid
from typing import Dict, List, Optional, Tuple

from persistence.database import database
from rules.logic import (
    apply_move,
    count_score,
    create_initial_board,
    get_valid_moves,
    is_valid_move,
    resolve_game_state,
)

PIECES_4P = ["black", "white", "red", "blue"]
TURN_ORDER_4P = ["black", "white", "red", "blue"]
BOARD_SIZE_4P = 16
DIRECTIONS_4P = [
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
]


def create_initial_board_4p() -> List[List[Optional[str]]]:
    board = [[None for _ in range(BOARD_SIZE_4P)] for _ in range(BOARD_SIZE_4P)]

    top_row = 3
    bottom_row = 11
    left_col = 3
    right_col = 11

    def place_cluster(
        start_row: int,
        start_col: int,
        top_left: str,
        top_right: str,
        bottom_left: str,
        bottom_right: str,
    ) -> None:
        board[start_row][start_col] = top_left
        board[start_row][start_col + 1] = top_right
        board[start_row + 1][start_col] = bottom_left
        board[start_row + 1][start_col + 1] = bottom_right

    # Superior izquierda
    place_cluster(top_row, left_col, "black", "white", "red", "blue")
    # Superior derecha
    place_cluster(top_row, right_col, "white", "black", "blue", "red")
    # Inferior izquierda
    place_cluster(bottom_row, left_col, "red", "blue", "black", "white")
    # Inferior derecha
    place_cluster(bottom_row, right_col, "blue", "red", "white", "black")

    return board


def is_inside_4p(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE_4P and 0 <= col < BOARD_SIZE_4P


def get_flips_4p(board: List[List[Optional[str]]], row: int, col: int, piece: str) -> List[Tuple[int, int]]:
    if board[row][col] is not None:
        return []

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
                line.append((r, c))
                r += dr
                c += dc
                continue
            break

        if line and is_inside_4p(r, c) and board[r][c] == piece:
            flips.extend(line)

    return flips


def get_valid_moves_4p(board: List[List[Optional[str]]], piece: str) -> List[Dict[str, int]]:
    moves: List[Dict[str, int]] = []
    for row in range(BOARD_SIZE_4P):
        for col in range(BOARD_SIZE_4P):
            if get_flips_4p(board, row, col, piece):
                moves.append({"row": row, "col": col})
    return moves


def count_score_4p(board: List[List[Optional[str]]]) -> Dict[str, int]:
    score = {piece: 0 for piece in PIECES_4P}
    for row in board:
        for cell in row:
            if cell in score:
                score[cell] += 1
    return score


class GameManager:
    def __init__(self):
        self.active_games: Dict[str, dict] = {}

    def create_game(
        self,
        creator_name: str,
        is_private: bool = False,
        game_id: str = None,
        mode: str = "1v1",
        invited_name: str = None,
        participants: Optional[List[str]] = None,
    ) -> str:
        if not game_id:
            game_id = str(uuid.uuid4())

        normalized_mode = mode
        if normalized_mode == "1vs1":
            normalized_mode = "1v1"
        elif normalized_mode in ("1vs1vs1vs1", "1v1v1v1"):
            normalized_mode = "1v1v1v1"

        participant_list: List[str] = [name for name in (participants or []) if name]
        if not participant_list:
            participant_list = [creator_name]
            if invited_name:
                participant_list.append(invited_name)

        if normalized_mode == "1v1v1v1":
            board = create_initial_board_4p()
            expected_count = 4
            username_by_piece: Dict[str, Optional[str]] = {piece: None for piece in PIECES_4P}
            piece_by_username: Dict[str, str] = {}
            for idx, username in enumerate(participant_list[:4]):
                piece = TURN_ORDER_4P[idx]
                username_by_piece[piece] = username
                piece_by_username[username] = piece

            players_ready = {username: False for username in participant_list[:4]}
            game = {
                "game_id": game_id,
                "creator": creator_name,
                "mode": normalized_mode,
                "status": "waiting",
                "board": board,
                "current_player": "black",
                "winner": None,
                "game_over": False,
                "score": count_score_4p(board),
                "valid_moves": get_valid_moves_4p(board, "black"),
                "last_move": None,
                "db_game_id": None,
                "saved": False,
                "players_ready": players_ready,
                "participants": participant_list[:4],
                "participant_count_expected": expected_count,
                "turn_order": list(TURN_ORDER_4P),
                "username_by_piece": username_by_piece,
                "piece_by_username": piece_by_username,
                "active_pieces": [piece for piece, username in username_by_piece.items() if username],
                "abandoned_pieces": [],
                "final_positions": {},
                "black_player": username_by_piece["black"],
                "white_player": username_by_piece["white"],
                "red_player": username_by_piece["red"],
                "blue_player": username_by_piece["blue"],
            }
            self.active_games[game_id] = game
            return game_id

        board = create_initial_board()
        expected_count = 1 if normalized_mode == "vs_ai" else 2

        black_player = participant_list[0] if participant_list else creator_name
        white_player = "IA" if normalized_mode == "vs_ai" else (participant_list[1] if len(participant_list) > 1 else None)

        players_ready = {black_player: False}
        if white_player and white_player != "IA":
            players_ready[white_player] = False
        if white_player == "IA":
            players_ready["IA"] = True

        self.active_games[game_id] = {
            "game_id": game_id,
            "creator": creator_name,
            "mode": normalized_mode,
            "status": "playing" if normalized_mode == "vs_ai" else "waiting",
            "board": board,
            "current_player": "black",
            "winner": None,
            "game_over": False,
            "score": count_score(board),
            "valid_moves": [move.dict() for move in get_valid_moves(board, "black")],
            "last_move": None,
            "db_game_id": None,
            "black_player": black_player,
            "white_player": white_player,
            "saved": False,
            "players_ready": players_ready,
            "participants": [name for name in [black_player, white_player] if name and name != "IA"],
            "participant_count_expected": expected_count,
        }
        return game_id

    def set_game_playing(self, game_id: str, db_game_id: int = None, player1_id: int = None, player2_id: int = None):
        if game_id in self.active_games:
            self.active_games[game_id]["status"] = "playing"
            if db_game_id:
                self.active_games[game_id]["db_game_id"] = db_game_id

    def get_game_state(self, game_id: str) -> dict:
        return self.active_games.get(game_id)

    def remove_game(self, game_id: str):
        if game_id in self.active_games:
            del self.active_games[game_id]

    def set_player_ready(self, game_id: str, username: str, ready: bool):
        game = self.active_games.get(game_id)
        if not game:
            return
        game.setdefault("players_ready", {})
        game["players_ready"][username] = ready

    def are_all_players_ready(self, game_id: str) -> bool:
        game = self.active_games.get(game_id)
        if not game or game.get("status") != "waiting":
            return False

        participants = game.get("participants", [])
        expected_count = game.get("participant_count_expected", 2)
        if len(participants) != expected_count:
            return False

        ready_map = game.get("players_ready", {})
        return all(bool(ready_map.get(username, False)) for username in participants)

    def _next_piece_with_moves_4p(self, game: dict, start_piece: str) -> Optional[str]:
        turn_order: List[str] = game["turn_order"]
        active_pieces: List[str] = [p for p in turn_order if p in game.get("active_pieces", [])]
        if not active_pieces:
            return None

        start_idx = turn_order.index(start_piece) if start_piece in turn_order else -1
        for step in range(1, len(turn_order) + 1):
            piece = turn_order[(start_idx + step) % len(turn_order)]
            if piece not in active_pieces:
                continue
            moves = get_valid_moves_4p(game["board"], piece)
            if moves:
                return piece
        return None

    def _no_piece_can_move_4p(self, game: dict) -> bool:
        for piece in game.get("active_pieces", []):
            if get_valid_moves_4p(game["board"], piece):
                return False
        return True

    def _finalize_if_finished_4p(self, game: dict) -> None:
        active_pieces: List[str] = game.get("active_pieces", [])
        if len(active_pieces) <= 1:
            game["game_over"] = True
            game["status"] = "finished"
            game["current_player"] = None
            game["valid_moves"] = []
            game["winner"] = active_pieces[0] if active_pieces else "draw"
            return

        if self._no_piece_can_move_4p(game):
            game["game_over"] = True
            game["status"] = "finished"
            game["current_player"] = None
            game["valid_moves"] = []
            score = count_score_4p(game["board"])
            best = max((score.get(piece, 0) for piece in active_pieces), default=0)
            leaders = [piece for piece in active_pieces if score.get(piece, 0) == best]
            game["winner"] = leaders[0] if len(leaders) == 1 else "draw"

    async def make_move(self, game_id: str, player: str, row: int, col: int) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game:
            return False, "Partida no encontrada"
        if game["status"] == "waiting":
            return False, "La partida aun no ha empezado"
        if game["game_over"]:
            return False, "La partida ya ha terminado"

        if game.get("mode") == "1v1v1v1":
            if player not in PIECES_4P:
                return False, "Color de jugador invalido"
            if player not in game.get("active_pieces", []):
                return False, "Jugador no activo en la partida"
            if game["current_player"] != player:
                return False, "No es tu turno"
            if not is_inside_4p(row, col):
                return False, "Movimiento fuera del tablero"

            flips = get_flips_4p(game["board"], row, col, player)
            if not flips:
                return False, "Movimiento invalido"

            game["board"][row][col] = player
            for flip_row, flip_col in flips:
                game["board"][flip_row][flip_col] = player

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
                game["valid_moves"] = []
                game["winner"] = "draw"
                await self.save_game_results(game_id)
                return True, "Movimiento realizado"

            game["current_player"] = next_piece
            game["valid_moves"] = get_valid_moves_4p(game["board"], next_piece)
            return True, "Movimiento realizado"

        if game["current_player"] != player:
            return False, "No es tu turno"
        if not is_valid_move(game["board"], player, row, col):
            return False, "Movimiento invalido"

        game["board"] = apply_move(game["board"], player, row, col)
        game["last_move"] = {"row": row, "col": col}

        next_player = "white" if player == "black" else "black"
        over, winner, current, valid = resolve_game_state(game["board"], next_player)

        game["game_over"] = over
        game["winner"] = winner
        game["current_player"] = current
        game["valid_moves"] = [move.dict() for move in valid]
        game["score"] = count_score(game["board"])

        if over:
            game["status"] = "finished"

        return True, "Movimiento realizado"

    async def surrender_game(self, game_id: str, player: str) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game:
            return False, "Partida no encontrada"
        if game["status"] == "waiting":
            return False, "La partida aun no ha empezado"
        if game["game_over"]:
            return False, "La partida ya ha terminado"

        if game.get("mode") == "1v1v1v1":
            username = game.get("username_by_piece", {}).get(player, player)
            return await self.abandon_game(game_id, username)

        game["game_over"] = True
        game["winner"] = "white" if player == "black" else "black"
        game["current_player"] = None
        game["valid_moves"] = []
        game["status"] = "finished"

        await self.save_game_results(game_id)
        return True, "Te has rendido"

    async def abandon_game(self, game_id: str, disconnected_username: str) -> Tuple[bool, str]:
        game = self.active_games.get(game_id)
        if not game or game["game_over"] or game["status"] != "playing":
            return False, "La partida no es susceptible de abandono"

        if game.get("mode") == "1v1v1v1":
            piece = game.get("piece_by_username", {}).get(disconnected_username)
            if not piece:
                return False, "Jugador no encontrado en esta partida"
            if piece not in game.get("active_pieces", []):
                return False, "Jugador no activo en esta partida"

            game["active_pieces"] = [p for p in game["active_pieces"] if p != piece]
            if piece not in game.get("abandoned_pieces", []):
                game.setdefault("abandoned_pieces", []).append(piece)

            if piece not in game.get("final_positions", {}):
                # Requisito funcional: quien abandona se registra como 4º puesto.
                game.setdefault("final_positions", {})[piece] = 4

            game["score"] = count_score_4p(game["board"])

            self._finalize_if_finished_4p(game)
            if game["game_over"]:
                await self.save_game_results(game_id)
                return True, f"{disconnected_username} abandono la partida"

            if game.get("current_player") == piece:
                next_piece = self._next_piece_with_moves_4p(game, piece)
                if next_piece is None:
                    game["game_over"] = True
                    game["status"] = "finished"
                    game["current_player"] = None
                    game["valid_moves"] = []
                    game["winner"] = "draw"
                    await self.save_game_results(game_id)
                    return True, f"{disconnected_username} abandono la partida"
                game["current_player"] = next_piece
                game["valid_moves"] = get_valid_moves_4p(game["board"], next_piece)

            return True, f"{disconnected_username} abandono la partida"

        if game.get("black_player") == disconnected_username:
            game["winner"] = "white"
        elif game.get("white_player") == disconnected_username:
            game["winner"] = "black"
        else:
            return False, "Jugador no encontrado en esta partida"

        game["game_over"] = True
        game["current_player"] = None
        game["valid_moves"] = []
        game["status"] = "finished"

        await self.save_game_results(game_id)
        return True, f"{disconnected_username} abandono la partida"

    async def _save_game_results_1v1(self, game: dict) -> None:
        black_name = game.get("black_player")
        white_name = game.get("white_player")
        winner_color = game.get("winner")
        mode = game.get("mode", "1v1")
        score = game.get("score", {"black": 0, "white": 0})

        score_str_black = f"{score['black']}-{score['white']}"
        score_str_white = f"{score['white']}-{score['black']}"

        async def get_user_data(username: Optional[str]):
            if not username or username == "IA":
                return None
            return await database.fetch_one("SELECT id, elo FROM users WHERE username = :un", {"un": username})

        black_user = await get_user_data(black_name)
        white_user = await get_user_data(white_name)

        black_elo = black_user["elo"] if black_user else 1000
        white_elo = white_user["elo"] if white_user else 1000

        expected_black = 1 / (1 + 10 ** ((white_elo - black_elo) / 400))
        expected_white = 1 / (1 + 10 ** ((black_elo - white_elo) / 400))

        k_factor = 32

        if winner_color == "black":
            s_black, s_white = 1, 0
            res_black, res_white = "Ganada", "Perdida"
        elif winner_color == "white":
            s_black, s_white = 0, 1
            res_black, res_white = "Perdida", "Ganada"
        else:
            s_black, s_white = 0.5, 0.5
            res_black, res_white = "Empate", "Empate"

        black_change = int(k_factor * (s_black - expected_black)) if black_user else 0
        white_change = int(k_factor * (s_white - expected_white)) if white_user else 0

        if black_user:
            new_elo = black_elo + black_change
            await database.execute(
                "UPDATE users SET elo = :elo, peak_elo = GREATEST(COALESCE(peak_elo, elo), :elo) WHERE id = :uid",
                {"elo": new_elo, "uid": black_user["id"]},
            )
            await database.execute(
                """
                INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color)
                VALUES (:uid, :opp, :mode, :res, :score, :rc, 'black')
                """,
                {
                    "uid": black_user["id"],
                    "opp": white_name or "IA",
                    "mode": mode,
                    "res": res_black,
                    "score": score_str_black,
                    "rc": f"{black_change:+} RR",
                },
            )

        if white_user:
            new_elo = white_elo + white_change
            await database.execute(
                "UPDATE users SET elo = :elo, peak_elo = GREATEST(COALESCE(peak_elo, elo), :elo) WHERE id = :uid",
                {"elo": new_elo, "uid": white_user["id"]},
            )
            await database.execute(
                """
                INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color)
                VALUES (:uid, :opp, :mode, :res, :score, :rc, 'white')
                """,
                {
                    "uid": white_user["id"],
                    "opp": black_name or "IA",
                    "mode": mode,
                    "res": res_white,
                    "score": score_str_white,
                    "rc": f"{white_change:+} RR",
                },
            )

    def _compute_positions_4p(self, game: dict) -> Dict[str, int]:
        score = count_score_4p(game["board"])
        game["score"] = score

        positions = dict(game.get("final_positions", {}))
        remaining = [piece for piece in PIECES_4P if game.get("username_by_piece", {}).get(piece) and piece not in positions]
        remaining.sort(key=lambda piece: (-score.get(piece, 0), TURN_ORDER_4P.index(piece)))

        available_positions = [pos for pos in [1, 2, 3, 4] if pos not in positions.values()]
        for piece, pos in zip(remaining, available_positions):
            positions[piece] = pos

        return positions

    async def _save_game_results_4p(self, game: dict) -> None:
        positions = self._compute_positions_4p(game)
        rr_by_position = {1: 50, 2: 25, 3: 0, 4: -25}
        score = game.get("score", count_score_4p(game["board"]))

        participants = [username for username in game.get("participants", []) if username]
        users_by_username: Dict[str, dict] = {}
        for username in participants:
            row = await database.fetch_one("SELECT id, elo FROM users WHERE username = :un", {"un": username})
            if row:
                users_by_username[username] = row

        for piece in PIECES_4P:
            username = game.get("username_by_piece", {}).get(piece)
            if not username or username not in users_by_username:
                continue

            user_row = users_by_username[username]
            position = positions.get(piece, 4)
            rr_delta = rr_by_position.get(position, -25)
            new_elo = max(0, user_row["elo"] + rr_delta)

            opponents = [name for name in participants if name != username]
            opponent_name = ", ".join(opponents) if opponents else "N/A"

            await database.execute(
                "UPDATE users SET elo = :elo, peak_elo = GREATEST(COALESCE(peak_elo, elo), :elo) WHERE id = :uid",
                {"elo": new_elo, "uid": user_row["id"]},
            )
            await database.execute(
                """
                INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color)
                VALUES (:uid, :opp, :mode, :res, :score, :rc, :player_color)
                """,
                {
                    "uid": user_row["id"],
                    "opp": opponent_name,
                    "mode": "1vs1vs1vs1",
                    "res": f"{position}º",
                    "score": f"{position}º puesto · {score.get(piece, 0)} pts",
                    "rc": f"{rr_delta:+} RR",
                    "player_color": piece,
                },
            )

    async def save_game_results(self, game_id: str):
        game = self.active_games.get(game_id)
        if not game or game.get("saved"):
            return

        game["saved"] = True
        if game.get("mode") == "1v1v1v1":
            await self._save_game_results_4p(game)
            return

        await self._save_game_results_1v1(game)


game_manager = GameManager()
