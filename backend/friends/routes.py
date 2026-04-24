from fastapi import APIRouter, HTTPException, Depends
from persistence.database import database
from auth.dependencies import get_current_user
from friends.schemas import FriendRequest, ChatMessageCreate
from game.manager import game_manager
from ws.manager import manager as ws_manager
from ws.notifications import notifier

router = APIRouter()



async def assert_accepted_friendship(current_user_id: int, friend_id: int):
    friendship = await database.fetch_one(
        """
        SELECT 1
        FROM friendships
        WHERE status = 'accepted'
          AND ((user_id = :uid AND friend_id = :fid) OR (user_id = :fid AND friend_id = :uid))
        LIMIT 1
        """,
        values={"uid": current_user_id, "fid": friend_id},
    )
    if not friendship:
        raise HTTPException(status_code=403, detail="Solo puedes chatear con amigos aceptados")


@router.get("")
async def list_friends(current_user: dict = Depends(get_current_user)):
    # 1. Amigos aceptados
    query_friends = """
        SELECT
            u.id,
            u.username as name,
            u.elo as rr,
            u.avatar_url as avatar_url,
            COALESCE((
                SELECT COUNT(*)
                FROM friend_messages fm
                WHERE fm.sender_id = u.id
                  AND fm.receiver_id = :uid
                  AND fm.is_read = false
            ), 0) AS unread_count
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
        SELECT
            u.id,
            u.username as name,
            u.elo as rr,
            u.avatar_url as avatar_url,
            l.mode as gameMode,
            l.id as lobby_id
        FROM lobbies l
        JOIN users u ON l.creator_id = u.id
        JOIN lobby_invites li ON li.lobby_id = l.id
        WHERE COALESCE(li.invited_id, li.invited_user_id) = :uid
          AND li.status = 'pending'
          AND l.status = 'waiting'
          AND l.is_public = false
        ORDER BY l.created_at DESC
    """
    game_invites_rows = await database.fetch_all(query=query_game_invites, values={"uid": current_user["id"]})

    paused_games = []
    paused_modes_supported = {
        "1v1", "1vs1", "1v1_skills", "1vs1_skills",
        "1v1v1v1", "1vs1vs1vs1", "1v1v1v1_skills", "1vs1vs1vs1_skills",
    }
    current_username = current_user["username"]
    for game_id, game in game_manager.active_games.items():
        mode = (game.get("mode") or "").lower()
        if mode not in paused_modes_supported:
            continue
        if not game.get("is_private"):
            continue
        if game.get("status") != "playing" or game.get("game_over"):
            continue
        participants = [u for u in game.get("participants", []) if u]
        if current_username not in participants:
            continue
        paused_usernames = list(game.get("paused_usernames", []))
        if current_username not in paused_usernames:
            continue

        is_four_player = mode.replace("_skills", "") in ("1v1v1v1", "1vs1vs1vs1")

        if is_four_player:
            username_by_piece = game.get("username_by_piece", {})
            active_usernames = [
                username_by_piece.get(piece)
                for piece in game.get("active_pieces", [])
                if username_by_piece.get(piece)
            ]
        else:
            active_usernames = list(participants)

        remaining_others = [u for u in active_usernames if u != current_username]
        if not remaining_others:
            continue

        paused_games.append({
            "game_id": int(game_id),
            "mode": "1vs1vs1vs1_skills" if mode in ("1v1v1v1_skills", "1vs1vs1vs1_skills") else ("1vs1vs1vs1" if is_four_player else ("1vs1_skills" if mode in ("1v1_skills", "1vs1_skills") else "1vs1")),
            "participants": participants,
            "paused_by": paused_usernames,
            "active_players": active_usernames,
        })

    online_friends = []
    offline_friends = []
    for row in friends_rows:
        friend_data = dict(row)
        friend_username = friend_data.get("name", "")
        if friend_username in ws_manager.active_users or friend_username in notifier.active_users:
            friend_data["status"] = "online"
            online_friends.append(friend_data)
        else:
            friend_data["status"] = "offline"
            offline_friends.append(friend_data)

    return {
        "online": online_friends,
        "offline": offline_friends,
        "requests": [dict(row) for row in requests_rows],
        "gameRequests": [dict(row) for row in game_invites_rows],
        "pausedGames": paused_games
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


@router.get("/{user_id}/chat")
async def get_friend_chat(user_id: int, current_user: dict = Depends(get_current_user)):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="No puedes abrir un chat contigo mismo")

    await assert_accepted_friendship(current_user["id"], user_id)

    rows = await database.fetch_all(
        """
        SELECT
            fm.id,
            fm.sender_id,
            su.username AS sender_name,
            fm.receiver_id,
            ru.username AS receiver_name,
            fm.message,
            fm.is_read,
            fm.created_at
        FROM friend_messages fm
        JOIN users su ON su.id = fm.sender_id
        JOIN users ru ON ru.id = fm.receiver_id
        WHERE (fm.sender_id = :uid AND fm.receiver_id = :fid)
           OR (fm.sender_id = :fid AND fm.receiver_id = :uid)
        ORDER BY fm.created_at ASC, fm.id ASC
        """,
        values={"uid": current_user["id"], "fid": user_id},
    )

    return {"messages": [dict(row) for row in rows]}


@router.post("/{user_id}/chat")
async def send_friend_chat_message(
    user_id: int,
    payload: ChatMessageCreate,
    current_user: dict = Depends(get_current_user),
):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="No puedes enviarte mensajes a ti mismo")

    await assert_accepted_friendship(current_user["id"], user_id)

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio")
    if len(message) > 1000:
        raise HTTPException(status_code=400, detail="El mensaje es demasiado largo (maximo 1000 caracteres)")

    row = await database.fetch_one(
        """
        INSERT INTO friend_messages (sender_id, receiver_id, message, is_read)
        VALUES (:uid, :fid, :message, false)
        RETURNING id, sender_id, receiver_id, message, is_read, created_at
        """,
        values={"uid": current_user["id"], "fid": user_id, "message": message},
    )

    return {"message": dict(row)}


@router.post("/{user_id}/chat/read")
async def mark_friend_chat_as_read(user_id: int, current_user: dict = Depends(get_current_user)):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Operacion invalida")

    await assert_accepted_friendship(current_user["id"], user_id)

    await database.execute(
        """
        UPDATE friend_messages
        SET is_read = true
        WHERE sender_id = :fid
          AND receiver_id = :uid
          AND is_read = false
        """,
        values={"uid": current_user["id"], "fid": user_id},
    )

    return {"message": "Mensajes marcados como leidos"}
