import uuid
from fastapi import APIRouter, Depends, HTTPException
from auth.dependencies import get_current_user
from game.manager import game_manager
from persistence.database import database

router = APIRouter()

@router.post("/create")
async def create_public_lobby(current_user: dict = Depends(get_current_user)):
    """El creador pide abrir una sala pública online."""
    query = "INSERT INTO lobbies (creator_id, is_public, status) VALUES (:creator_id, true, 'waiting') RETURNING id"
    lobby_id = await database.execute(query=query, values={"creator_id": current_user["id"]})
    game_id = str(lobby_id)
    
    game_manager.create_game(creator_name=current_user["username"], game_id=game_id)
    return {"game_id": game_id, "creator": current_user["username"]}

@router.get("/public")
async def get_public_lobbies():
    """El Jugador 2 llama a esto para ver qué salas existen."""
    query = """
        SELECT l.id as game_id, u.username as creator 
        FROM lobbies l 
        JOIN users u ON l.creator_id = u.id 
        WHERE l.status = 'waiting' AND l.is_public = true
    """
    rows = await database.fetch_all(query=query)
    
    lobbies = []
    for r in rows:
        g_id = str(r["game_id"])
        # Si el server crasheó, reinicializar sala en memoria
        if g_id not in game_manager.active_games:
            game_manager.create_game(creator_name=r["creator"], is_private=False, game_id=g_id)
        lobbies.append({"game_id": g_id, "creator": r["creator"]})
        
    return {"lobbies": lobbies}

@router.post("/join/{game_id}")
async def join_public_lobby(game_id: str, current_user: dict = Depends(get_current_user)):
    """El Jugador 2 se une a una sala pública existente."""
    query = """
        UPDATE lobbies 
        SET status = 'playing'
        WHERE id = :id AND status = 'waiting' AND is_public = true
        RETURNING id, creator_id
    """
    lobby = await database.fetch_one(query=query, values={"id": int(game_id)})
    
    if not lobby:
        raise HTTPException(status_code=400, detail="La sala ya está llena o no existe.")

    # Marcamos la sala como en juego en la memoria RAM
    game_manager.set_game_playing(game_id)
    
    return {"status": "success", "game_id": game_id, "message": "Te has unido a la partida"}

@router.post("/invite")
async def invite_friend(target_username: str, current_user: dict = Depends(get_current_user)):
    #faltaria implementar que el usuario no se pueda invitar a si mismo y que el usuario invitado exista
    #ademas de que ambos usuarios sean amigos(esta verificacion falta en general en la mayoria que he hecho ahora) 
    """Crea una sala privada y envía el desafío por WS."""
    from ws.notifications import notifier
    query = "INSERT INTO lobbies (creator_id, is_public, status) VALUES (:creator_id, false, 'waiting') RETURNING id"
    lobby_id = await database.execute(query=query, values={"creator_id": current_user["id"]})
    game_id = str(lobby_id)
    
    success = await notifier.send_invite(target_username=target_username, creator=current_user["username"], game_id=game_id)        
    return {"game_id": game_id, "creator": current_user["username"], "invite_sent": success}

@router.post("/{game_id}/accept")
async def accept_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    """Aceptar un desafío privado."""
    query = "SELECT l.id, u.username as creator FROM lobbies l JOIN users u ON l.creator_id = u.id WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false"
    lobby = await database.fetch_one(query=query, values={"id": int(game_id)})
    
    if not lobby:
        raise HTTPException(status_code=400, detail="El desafío ya no está disponible.")
        
    #Marcar como playing
    update_query = "UPDATE lobbies SET status = 'playing' WHERE id = :id RETURNING id"
    await database.execute(query=update_query, values={"id": int(game_id)})

    #Crear partida
    game_manager.create_game(creator_name=lobby["creator"], is_private=True, game_id=game_id)
    game_manager.set_game_playing(game_id)

    #Avisar al creador
    from ws.notifications import notifier
    await notifier.send_invite_response(target_username=lobby["creator"], game_id=game_id, action="accepted", guest=current_user["username"])
    
    return {"status": "success", "game_id": game_id}

@router.post("/{game_id}/reject")
async def reject_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    """Rechazar un desafío privado."""
    query = "SELECT l.id, u.username as creator FROM lobbies l JOIN users u ON l.creator_id = u.id WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false"
    lobby = await database.fetch_one(query=query, values={"id": int(game_id)})
    
    if not lobby:
        raise HTTPException(status_code=400, detail="El desafío no existe.")
        
    #Borrar la sala de RAM y BBBD
    delete_query = "DELETE FROM lobbies WHERE id = :id"
    await database.execute(query=delete_query, values={"id": int(game_id)})
    
    from ws.notifications import notifier
    await notifier.send_invite_response(target_username=lobby["creator"], game_id=game_id, action="rejected", guest=current_user["username"])
    
    return {"status": "success"}