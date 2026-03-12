from typing import List, Optional, Literal
from pydantic import BaseModel

Player = Literal['black', 'white']
Cell = Optional[Player]
Board = List[List[Cell]]
BOARD_SIZE = 8

class Coordinate(BaseModel):
    row: int
    col: int