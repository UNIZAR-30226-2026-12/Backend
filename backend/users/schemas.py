from pydantic import BaseModel
from typing import Optional

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None

class CustomizationUpdate(BaseModel):
    avatar_url: Optional[str] = None
    preferred_piece_color: Optional[str] = None
    preferred_board_color: Optional[str] = None

class EloUpdate(BaseModel):
    elo: int

class GameHistoryCreate(BaseModel):
    opponent_name: str
    mode: str
    result: str
    score: str
    rankChange: str
    player_color: Optional[str] = "black"   # 'black' | 'white'

class GameHistoryResponse(BaseModel):
    id: int
    date: str
    mode: str
    result: str
    score: str
    rankChange: str
    player_color: Optional[str] = None
