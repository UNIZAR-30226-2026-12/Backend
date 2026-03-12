from pydantic import BaseModel
from typing import List, Optional, Dict
from rules.schemas import Player, Board, Coordinate

class GameStateResponse(BaseModel):
    game_id: str
    board: Board
    current_player: Optional[Player]
    winner: Optional[str]
    game_over: bool
    score: Dict[str, int]
    valid_moves: List[Coordinate]
    last_move: Optional[Coordinate] = None

class MoveRequest(BaseModel):
    game_id: str
    row: int
    col: int
    player: Player