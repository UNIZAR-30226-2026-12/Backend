from fastapi import APIRouter, Depends
from persistence.database import database
from auth.dependencies import get_current_user
from lobby.schemas import GameInviteRequest

router = APIRouter()

@router.post("/invite")
async def invite_to_game(req: GameInviteRequest, current_user: dict = Depends(get_current_user)):
    # Crear un lobby privado con invitado
    query = """
        INSERT INTO lobbies (creator_id, invited_id, is_public, mode, status)
        VALUES (:cid, :iid, false, :mode, 'waiting')
        RETURNING id
    """
    lobby_id = await database.execute(query=query, values={
        "cid": current_user["id"],
        "iid": req.friend_id,
        "mode": req.mode
    })
    return {"lobby_id": lobby_id}