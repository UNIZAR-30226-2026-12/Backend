from fastapi import APIRouter, HTTPException, Depends
from persistence.database import database
from auth.dependencies import get_current_user
from friends.schemas import FriendRequest

router = APIRouter()

@router.get("/")
async def list_friends(current_user: dict = Depends(get_current_user)):
    # 1. Amigos aceptados
    query_friends = """
        SELECT u.id, u.username as name, u.elo as rr, u.avatar_url as avatar_url
        FROM users u
        JOIN friendships f ON (f.friend_id = u.id AND f.user_id = :uid) OR (f.user_id = u.id AND f.friend_id = :uid)
        WHERE f.status = 'accepted'
    """
    friends_rows = await database.fetch_all(query=query_friends, values={"uid": current_user["id"]})
    
    # 2. Solicitudes recibidas pendientes
    query_requests = """
        SELECT u.id, u.username as name, u.elo as rr, u.avatar_url as avatar_url
        FROM users u
        JOIN friendships f ON f.user_id = u.id
        WHERE f.friend_id = :uid AND f.status = 'pending'
    """
    requests_rows = await database.fetch_all(query=query_requests, values={"uid": current_user["id"]})
    
    # 3. Invitaciones a juegos (de lobbies donde estamos invitados)
    query_game_invites = """
        SELECT u.id, u.username as name, u.elo as rr, u.avatar_url as avatar_url, l.mode as gameMode, l.id as lobby_id
        FROM users u
        JOIN lobbies l ON l.creator_id = u.id
        WHERE l.invited_id = :uid AND l.status = 'waiting'
    """
    game_invites_rows = await database.fetch_all(query=query_game_invites, values={"uid": current_user["id"]})

    return {
        "friends": [
            {**dict(row), "status": "online"} for row in friends_rows # Mock status online
        ],
        "requests": [dict(row) for row in requests_rows],
        "gameRequests": [dict(row) for row in game_invites_rows]
    }

@router.post("/request")
async def send_friend_request(req: FriendRequest, current_user: dict = Depends(get_current_user)):
    # Buscar el usuario por username
    query_user = "SELECT id FROM users WHERE username = :un"
    target_user = await database.fetch_one(query=query_user, values={"un": req.username})
    
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if target_user["id"] == current_user["id"]:
        raise HTTPException(status_code=400, detail="No puedes enviarte una solicitud a ti mismo")
    
    # Verificar si ya existe una relación
    query_check = "SELECT status FROM friendships WHERE (user_id = :uid AND friend_id = :tid) OR (user_id = :tid AND friend_id = :uid)"
    existing = await database.fetch_one(query=query_check, values={"uid": current_user["id"], "tid": target_user["id"]})
    
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una relación con este usuario")
    
    # Verificar si ha sido rechazado demasiadas veces (límite de 3)
    query_rejections = "SELECT rejection_count FROM friend_request_rejections WHERE sender_id = :uid AND receiver_id = :tid"
    rejection = await database.fetch_one(query=query_rejections, values={"uid": current_user["id"], "tid": target_user["id"]})
    if rejection and rejection["rejection_count"] >= 3:
        raise HTTPException(status_code=403, detail="No puedes enviar más solicitudes a este usuario, has sido rechazado demasiadas veces.")
    
    query_insert = "INSERT INTO friendships (user_id, friend_id, status) VALUES (:uid, :tid, 'pending')"
    await database.execute(query=query_insert, values={"uid": current_user["id"], "tid": target_user["id"]})
    
    return {"message": "Solicitud enviada"}

@router.post("/{user_id}/accept")
async def accept_friend_request(user_id: int, current_user: dict = Depends(get_current_user)):
    query = "UPDATE friendships SET status = 'accepted' WHERE user_id = :tid AND friend_id = :uid AND status = 'pending'"
    await database.execute(query=query, values={"uid": current_user["id"], "tid": user_id})
    return {"message": "Solicitud aceptada"}

@router.post("/{user_id}/reject")
async def reject_friend_request(user_id: int, current_user: dict = Depends(get_current_user)):
    # Comprobar si era una solicitud pendiente para registrar el rechazo
    query_check = "SELECT status FROM friendships WHERE user_id = :tid AND friend_id = :uid"
    existing = await database.fetch_one(query=query_check, values={"uid": current_user["id"], "tid": user_id})
    
    if existing and existing["status"] == 'pending':
        # Es un rechazo de solicitud pendiente: sumar 1 al contador
        query_upsert = """
            INSERT INTO friend_request_rejections (sender_id, receiver_id, rejection_count)
            VALUES (:sender, :receiver, 1)
            ON CONFLICT (sender_id, receiver_id) 
            DO UPDATE SET rejection_count = friend_request_rejections.rejection_count + 1
        """
        await database.execute(query=query_upsert, values={"sender": user_id, "receiver": current_user["id"]})

    query = "DELETE FROM friendships WHERE (user_id = :tid AND friend_id = :uid) OR (user_id = :uid AND friend_id = :tid)"
    await database.execute(query=query, values={"uid": current_user["id"], "tid": user_id})
    return {"message": "Solicitud/Amigo eliminado"}

@router.delete("/{user_id}")
async def delete_friend(user_id: int, current_user: dict = Depends(get_current_user)):
    return await reject_friend_request(user_id, current_user)