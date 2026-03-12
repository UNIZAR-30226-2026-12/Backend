from pydantic import BaseModel

class FriendResponse(BaseModel):
    id: int
    name: str # username
    status: str # online, offline, playing
    rr: int # elo

class FriendRequest(BaseModel):
    username: str