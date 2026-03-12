from pydantic import BaseModel

class GameInviteRequest(BaseModel):
    friend_id: int
    mode: str # 1vs1, 1vs1vs1vs1