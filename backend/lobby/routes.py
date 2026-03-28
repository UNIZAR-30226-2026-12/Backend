from fastapi import APIRouter, Depends, HTTPException
from auth.dependencies import get_current_user
from game.manager import game_manager
from persistence.database import database
from pydantic import BaseModel

router = APIRouter()


class GameCreateRequest(BaseModel):
    mode: str = "1vs1"


class GameInviteRequest(BaseModel):
    friend_id: int
    mode: str = "1vs1"


class ReadyRequest(BaseModel):
    ready: bool


def normalize_mode(mode: str) -> str:
    return "1v1" if mode == "1vs1" else mode


@router.post("/create")
async def create_public_lobby(req: GameCreateRequest, current_user: dict = Depends(get_current_user)):
    is_public = req.mode == "1vs1"

    query = """
        INSERT INTO lobbies (creator_id, is_public, status, mode)
        VALUES (:creator_id, :is_public, 'waiting', :mode)
        RETURNING id
    """
    lobby_id = await database.fetch_val(
        query=query,
        values={"creator_id": current_user["id"], "is_public": is_public, "mode": req.mode},
    )
    game_id = str(lobby_id)

    game_manager.create_game(
        creator_name=current_user["username"],
        game_id=game_id,
        mode=normalize_mode(req.mode),
    )
    return {"game_id": game_id, "creator": current_user["username"], "mode": req.mode}


@router.get("/public")
async def get_public_lobbies():
    query = """
        SELECT l.id as game_id, u.username as creator, u.avatar_url, u.elo as creator_rr, l.mode
        FROM lobbies l
        JOIN users u ON l.creator_id = u.id
        WHERE l.status = 'waiting' AND l.is_public = true
    """
    rows = await database.fetch_all(query=query)

    lobbies = []
    for r in rows:
        g_id = str(r["game_id"])
        if g_id not in game_manager.active_games:
            game_manager.create_game(creator_name=r["creator"], game_id=g_id, mode=normalize_mode(r["mode"]))
        lobbies.append({
            "game_id": g_id,
            "creator": r["creator"],
            "avatar_url": r["avatar_url"],
            "creator_rr": r["creator_rr"],
            "mode": r["mode"],
        })

    return {"lobbies": lobbies}


@router.post("/join/{game_id}")
async def join_public_lobby(game_id: str, current_user: dict = Depends(get_current_user)):
    query = """
        UPDATE lobbies
        SET status = 'playing', invited_id = :uid
        WHERE id = :id AND status = 'waiting' AND is_public = true
        RETURNING id
    """
    lobby = await database.fetch_one(query=query, values={"id": int(game_id), "uid": current_user["id"]})
    if not lobby:
        raise HTTPException(status_code=400, detail="La sala ya está llena o no existe.")

    game = game_manager.get_game_state(game_id)
    if game:
        game["white_player"] = current_user["username"]
        game.setdefault("players_ready", {})
        game["players_ready"][current_user["username"]] = False

    return {"status": "success", "game_id": game_id}


@router.post("/invite")
async def invite_friend(req: GameInviteRequest, current_user: dict = Depends(get_current_user)):
    if req.friend_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="No puedes invitarte a ti mismo")

    friend = await database.fetch_one(
        "SELECT id, username, elo, avatar_url FROM users WHERE id = :fid",
        {"fid": req.friend_id},
    )
    if not friend:
        raise HTTPException(status_code=404, detail="Amigo no encontrado")

    friendship = await database.fetch_one(
        """
        SELECT 1
        FROM friendships
        WHERE status = 'accepted'
          AND ((user_id = :uid AND friend_id = :fid) OR (user_id = :fid AND friend_id = :uid))
        """,
        {"uid": current_user["id"], "fid": req.friend_id},
    )
    if not friendship:
        raise HTTPException(status_code=403, detail="Solo puedes invitar a usuarios que sean tus amigos")

    mode = req.mode if req.mode in ("1vs1", "1vs1vs1vs1") else "1vs1"
    lobby_id = await database.fetch_val(
        """
        INSERT INTO lobbies (creator_id, invited_id, is_public, status, mode)
        VALUES (:creator_id, :invited_id, false, 'waiting', :mode)
        RETURNING id
        """,
        {"creator_id": current_user["id"], "invited_id": req.friend_id, "mode": mode},
    )
    game_id = str(lobby_id)

    game_manager.create_game(
        creator_name=current_user["username"],
        is_private=True,
        game_id=game_id,
        mode=normalize_mode(mode),
    )

    from ws.notifications import notifier
    success = await notifier.send_invite(
        target_username=friend["username"],
        creator=current_user["username"],
        game_id=game_id,
        mode=mode,
    )
    return {
        "game_id": game_id,
        "creator": current_user["username"],
        "mode": mode,
        "invite_sent": success,
    }


@router.post("/{game_id}/accept")
async def accept_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one(
        """
        SELECT l.id, l.mode, l.creator_id, cu.username as creator_username
        FROM lobbies l
        JOIN users cu ON cu.id = l.creator_id
        WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false AND l.invited_id = :uid
        """,
        {"id": int(game_id), "uid": current_user["id"]},
    )
    if not lobby:
        raise HTTPException(status_code=400, detail="El desafío ya no está disponible.")

    game = game_manager.get_game_state(game_id)
    if not game:
        game_manager.create_game(
            creator_name=lobby["creator_username"],
            is_private=True,
            game_id=game_id,
            mode=normalize_mode(lobby["mode"]),
        )
        game = game_manager.get_game_state(game_id)

    if game:
        game["white_player"] = current_user["username"]
        game.setdefault("players_ready", {})
        game["players_ready"][lobby["creator_username"]] = False
        game["players_ready"][current_user["username"]] = False

    from ws.notifications import notifier
    await notifier.send_invite_response(
        target_username=lobby["creator_username"],
        game_id=game_id,
        action="accepted",
        guest=current_user["username"],
    )

    return {"status": "success", "game_id": game_id}


@router.post("/{game_id}/reject")
async def reject_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one(
        """
        SELECT l.id, cu.username as creator_username
        FROM lobbies l
        JOIN users cu ON cu.id = l.creator_id
        WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false AND l.invited_id = :uid
        """,
        {"id": int(game_id), "uid": current_user["id"]},
    )
    if not lobby:
        raise HTTPException(status_code=400, detail="El desafío no existe.")

    await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
    game_manager.remove_game(game_id)

    from ws.notifications import notifier
    await notifier.send_invite_response(
        target_username=lobby["creator_username"],
        game_id=game_id,
        action="rejected",
        guest=current_user["username"],
    )
    return {"status": "success"}


@router.post("/{game_id}/leave")
async def leave_lobby(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one(
        """
        SELECT l.id, l.creator_id, l.invited_id, cu.username as creator_username, iu.username as invited_username
        FROM lobbies l
        JOIN users cu ON cu.id = l.creator_id
        LEFT JOIN users iu ON iu.id = l.invited_id
        WHERE l.id = :id
        """,
        {"id": int(game_id)},
    )
    if not lobby:
        raise HTTPException(status_code=404, detail="La sala no existe")

    if current_user["id"] not in {lobby["creator_id"], lobby["invited_id"]}:
        raise HTTPException(status_code=403, detail="No perteneces a esta sala")

    other_username = lobby["invited_username"] if current_user["id"] == lobby["creator_id"] else lobby["creator_username"]
    await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
    game_manager.remove_game(game_id)

    if other_username:
        from ws.notifications import notifier
        await notifier.send_invite_response(
            target_username=other_username,
            game_id=game_id,
            action="left",
            guest=current_user["username"],
        )

    return {"status": "success"}


@router.get("/{game_id}/state")
async def get_lobby_state(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one(
        """
        SELECT l.id, l.status, l.mode, l.creator_id, l.invited_id
        FROM lobbies l
        WHERE l.id = :id
        """,
        {"id": int(game_id)},
    )
    if not lobby:
        raise HTTPException(status_code=404, detail="Sala no encontrada")

    if current_user["id"] not in {lobby["creator_id"], lobby["invited_id"]}:
        raise HTTPException(status_code=403, detail="No perteneces a esta sala")

    game = game_manager.get_game_state(game_id)
    ready = game.get("players_ready", {}) if game else {}
    usernames = []
    if game:
        if game.get("black_player"):
            usernames.append(game["black_player"])
        if game.get("white_player"):
            usernames.append(game["white_player"])

    players_rows = []
    if usernames:
        players_rows = await database.fetch_all(
            """
            SELECT id, username, elo, avatar_url
            FROM users
            WHERE username = ANY(:usernames)
            """,
            {"usernames": usernames},
        )

    return {
        "game_id": game_id,
        "status": game["status"] if game else lobby["status"],
        "mode": lobby["mode"],
        "players": [
            {
                "id": p["id"],
                "username": p["username"],
                "rr": p["elo"],
                "avatar_url": p["avatar_url"],
                "is_ready": bool(ready.get(p["username"], False)),
            }
            for p in players_rows
        ],
    }


@router.post("/{game_id}/ready")
async def set_ready(game_id: str, body: ReadyRequest, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one(
        "SELECT id, creator_id, invited_id FROM lobbies WHERE id = :id",
        {"id": int(game_id)},
    )
    if not lobby:
        raise HTTPException(status_code=404, detail="Sala no encontrada")
    if current_user["id"] not in {lobby["creator_id"], lobby["invited_id"]}:
        raise HTTPException(status_code=403, detail="No perteneces a esta sala")

    game = game_manager.get_game_state(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Sala en memoria no encontrada")

    game_manager.set_player_ready(game_id, current_user["username"], body.ready)
    if game_manager.are_all_players_ready(game_id):
        game_manager.set_game_playing(game_id)
        await database.execute("UPDATE lobbies SET status = 'playing' WHERE id = :id", {"id": int(game_id)})

    return {
        "status": "success",
        "ready": body.ready,
        "game_status": game_manager.get_game_state(game_id).get("status", "waiting"),
    }
