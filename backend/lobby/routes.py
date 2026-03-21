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