from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth.dependencies import get_current_user
from game.manager import game_manager
from ws.manager import manager
from ws.notifications import notifier

router = APIRouter()

class GameInviteRequest(BaseModel):
    friend_username: str

@router.post("/create")
async def create_public_lobby(current_user: dict = Depends(get_current_user)):
    """El creador pide abrir una sala. Se le devuelve el ID para que se conecte."""
    game_id = game_manager.create_game(creator_name=current_user["username"])
    return {"game_id": game_id, "creator": current_user["username"]}

@router.get("/public")
async def get_public_lobbies():
    """El Jugador 2 llama a esto para ver qué salas hay abiertas."""
    return {"lobbies": game_manager.get_waiting_lobbies()}

@router.post("/invite")
async def invite_friend(req: GameInviteRequest, current_user: dict = Depends(get_current_user)):
    game_id = game_manager.create_game(creator_name=current_user["username"], is_private=True)
    
    enviado = await notifier.send_invite(
        target_username=req.friend_username, 
        creator=current_user["username"], 
        game_id=game_id
    )
    
    if not enviado:
        return {
            "game_id": game_id, 
            "status": "pending", 
            "message": f"Sala creada, pero {req.friend_username} no está conectado."
        }
        
    return {
        "game_id": game_id, 
        "status": "sent", 
        "message": f"Invitación enviada a {req.friend_username}."
    }

@router.post("/invite/accept")
async def accept_duel(req: GameInviteRequest, current_user: dict = Depends(get_current_user)):
    for g_id, game in game_manager.active_games.items():
        if game["creator"] == req.friend_username and game["status"] == "private":
            return {"status": "success", "game_id": g_id}
    raise HTTPException(status_code=404, detail="La invitación ha expirado.")

@router.post("/invite/reject")
async def reject_duel(req: GameInviteRequest, current_user: dict = Depends(get_current_user)):
    for g_id, game in game_manager.active_games.items():
        if game["creator"] == req.friend_username and game["status"] == "private":
            # Si el creador está esperando en el WS de la partida, le avisamos del rechazo
            await manager.broadcast_game_state(g_id, {
                "type": "invite_rejected",
                "payload": {"message": f"{current_user['username']} ha rechazado el duelo."}
            })
            del game_manager.active_games[g_id] # Borramos la sala
            return {"status": "success", "message": "Duelo rechazado."}
    return {"status": "error", "message": "Invitación no encontrada."}