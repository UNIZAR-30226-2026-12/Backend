from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from game.manager import game_manager
from persistence.database import database
from ws.manager import manager as ws_manager
from ws.notifications import notifier

router = APIRouter()


class GameCreateRequest(BaseModel):
    mode: str = "1vs1"


class GameInviteRequest(BaseModel):
    friend_ids: List[int] = Field(default_factory=list)
    mode: str = "1vs1"


class ReadyRequest(BaseModel):
    ready: bool


def normalize_mode(mode: str) -> str:
    if mode == "1vs1":
        return "1v1"
    if mode in ("1vs1vs1vs1", "1v1v1v1"):
        return "1v1v1v1"
    return "1v1"


async def ensure_lobby_invites_table() -> None:
    await database.execute(
        """
        CREATE TABLE IF NOT EXISTS lobby_invites (
            id SERIAL PRIMARY KEY,
            lobby_id INTEGER NOT NULL REFERENCES lobbies(id) ON DELETE CASCADE,
            invited_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            invite_order INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lobby_id, invited_id)
        )
        """
    )
    await database.execute(
        """
        ALTER TABLE lobby_invites
        ADD COLUMN IF NOT EXISTS invited_id INTEGER REFERENCES users(id) ON DELETE CASCADE
        """
    )
    await database.execute(
        """
        ALTER TABLE lobby_invites
        ADD COLUMN IF NOT EXISTS invited_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
        """
    )
    await database.execute(
        """
        UPDATE lobby_invites
        SET invited_user_id = invited_id
        WHERE invited_user_id IS NULL AND invited_id IS NOT NULL
        """
    )
    await database.execute(
        """
        UPDATE lobby_invites
        SET invited_id = invited_user_id
        WHERE invited_id IS NULL AND invited_user_id IS NOT NULL
        """
    )
    await database.execute(
        """
        ALTER TABLE lobby_invites
        ADD COLUMN IF NOT EXISTS invite_order INTEGER NOT NULL DEFAULT 0
        """
    )
    await database.execute(
        """
        ALTER TABLE lobby_invites
        ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending'
        """
    )
    await database.execute(
        """
        ALTER TABLE lobby_invites
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        """
    )


async def get_lobby_participants(lobby_id: int) -> List[Dict]:
    lobby = await database.fetch_one(
        """
        SELECT l.id, l.creator_id, cu.username AS creator_username
        FROM lobbies l
        JOIN users cu ON cu.id = l.creator_id
        WHERE l.id = :id
        """,
        {"id": lobby_id},
    )
    if not lobby:
        return []

    invited_rows = await database.fetch_all(
        """
        SELECT COALESCE(li.invited_id, li.invited_user_id) AS invited_id, li.status, li.invite_order, u.username
        FROM lobby_invites li
        JOIN users u ON u.id = COALESCE(li.invited_id, li.invited_user_id)
        WHERE li.lobby_id = :id AND li.status = 'accepted'
        ORDER BY li.invite_order ASC
        """,
        {"id": lobby_id},
    )

    participants = [{
        "user_id": lobby["creator_id"],
        "username": lobby["creator_username"],
        "status": "accepted",
        "invite_order": 0,
        "is_creator": True,
    }]

    for row in invited_rows:
        participants.append({
            "user_id": row["invited_id"],
            "username": row["username"],
            "status": row["status"],
            "invite_order": int(row["invite_order"]) + 1,
            "is_creator": False,
        })

    return participants


async def get_game_or_create_from_lobby(lobby_id: int) -> Tuple[dict, dict]:
    lobby = await database.fetch_one(
        "SELECT id, creator_id, mode, status FROM lobbies WHERE id = :id",
        {"id": lobby_id},
    )
    if not lobby:
        raise HTTPException(status_code=404, detail="Sala no encontrada")

    game_id = str(lobby_id)
    game = game_manager.get_game_state(game_id)
    if game:
        return lobby, game

    participants = await get_lobby_participants(lobby_id)
    ordered_usernames = [p["username"] for p in sorted(participants, key=lambda p: p["invite_order"])]
    game_manager.create_game(
        creator_name=ordered_usernames[0],
        game_id=game_id,
        mode=normalize_mode(lobby["mode"]),
        participants=ordered_usernames,
    )
    game = game_manager.get_game_state(game_id)
    return lobby, game


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
        participants=[current_user["username"]],
    )
    return {"game_id": game_id, "creator": current_user["username"], "mode": req.mode}


@router.get("/public")
async def get_public_lobbies():
    query = """
        SELECT l.id AS game_id, u.username AS creator, u.avatar_url, u.elo AS creator_rr, l.mode
        FROM lobbies l
        JOIN users u ON l.creator_id = u.id
        WHERE l.status = 'waiting' AND l.is_public = true
    """
    rows = await database.fetch_all(query=query)

    lobbies = []
    for row in rows:
        g_id = str(row["game_id"])
        if g_id not in game_manager.active_games:
            game_manager.create_game(
                creator_name=row["creator"],
                game_id=g_id,
                mode=normalize_mode(row["mode"]),
                participants=[row["creator"]],
            )
        lobbies.append({
            "game_id": g_id,
            "creator": row["creator"],
            "avatar_url": row["avatar_url"],
            "creator_rr": row["creator_rr"],
            "mode": row["mode"],
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
        raise HTTPException(status_code=400, detail="La sala ya esta llena o no existe.")

    game = game_manager.get_game_state(game_id)
    if game:
        game["white_player"] = current_user["username"]
        game["participants"] = [game.get("black_player"), current_user["username"]]
        game["participants"] = [u for u in game["participants"] if u]
        game.setdefault("players_ready", {})
        game["players_ready"][current_user["username"]] = False
        game["participant_count_expected"] = 2

    return {"status": "success", "game_id": game_id}


@router.post("/invite")
async def invite_friend(req: GameInviteRequest, current_user: dict = Depends(get_current_user)):
    await ensure_lobby_invites_table()

    mode = req.mode if req.mode in ("1vs1", "1vs1vs1vs1") else "1vs1"
    expected_invites = 1 if mode == "1vs1" else 3

    friend_ids = list(dict.fromkeys(req.friend_ids))
    if len(friend_ids) != expected_invites:
        raise HTTPException(
            status_code=400,
            detail=f"Este modo requiere exactamente {expected_invites} invitacion(es).",
        )

    if current_user["id"] in friend_ids:
        raise HTTPException(status_code=400, detail="No puedes invitarte a ti mismo")

    friends = await database.fetch_all(
        """
        SELECT id, username, elo, avatar_url
        FROM users
        WHERE id = ANY(:ids)
        """,
        {"ids": friend_ids},
    )
    by_id = {row["id"]: row for row in friends}
    missing = [fid for fid in friend_ids if fid not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail="Algun amigo invitado no existe")

    for fid in friend_ids:
        friendship = await database.fetch_one(
            """
            SELECT 1
            FROM friendships
            WHERE status = 'accepted'
              AND ((user_id = :uid AND friend_id = :fid) OR (user_id = :fid AND friend_id = :uid))
            """,
            {"uid": current_user["id"], "fid": fid},
        )
        if not friendship:
            raise HTTPException(status_code=403, detail="Solo puedes invitar a usuarios que sean tus amigos")

    first_invited_id = friend_ids[0] if friend_ids else None
    lobby_id = await database.fetch_val(
        """
        INSERT INTO lobbies (creator_id, invited_id, is_public, status, mode)
        VALUES (:creator_id, :invited_id, false, 'waiting', :mode)
        RETURNING id
        """,
        {"creator_id": current_user["id"], "invited_id": first_invited_id, "mode": mode},
    )
    game_id = str(lobby_id)

    for invite_order, invited_id in enumerate(friend_ids):
        await database.execute(
            """
            INSERT INTO lobby_invites (lobby_id, invited_id, invited_user_id, invite_order, status)
            VALUES (:lobby_id, :invited_id, :invited_user_id, :invite_order, 'pending')
            """,
            {
                "lobby_id": lobby_id,
                "invited_id": invited_id,
                "invited_user_id": invited_id,
                "invite_order": invite_order,
            },
        )

    # Para 4 jugadores, la sala no debe aparecer llena hasta que acepten y entren.
    participants = [current_user["username"]]
    game_manager.create_game(
        creator_name=current_user["username"],
        is_private=True,
        game_id=game_id,
        mode=normalize_mode(mode),
        participants=participants,
    )

    invites_sent = 0
    for friend_id in friend_ids:
        sent = await notifier.send_invite(
            target_username=by_id[friend_id]["username"],
            creator=current_user["username"],
            game_id=game_id,
            mode=mode,
        )
        if sent:
            invites_sent += 1

    return {
        "game_id": game_id,
        "creator": current_user["username"],
        "mode": mode,
        "invites_sent": invites_sent,
    }


@router.post("/{game_id}/accept")
async def accept_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_lobby_invites_table()

    lobby = await database.fetch_one(
        """
        SELECT l.id, l.mode, l.creator_id, cu.username AS creator_username, li.status AS invite_status
        FROM lobbies l
        JOIN users cu ON cu.id = l.creator_id
        JOIN lobby_invites li ON li.lobby_id = l.id AND COALESCE(li.invited_id, li.invited_user_id) = :uid
        WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false
        """,
        {"id": int(game_id), "uid": current_user["id"]},
    )
    if not lobby:
        raise HTTPException(status_code=400, detail="La invitacion ya no esta disponible.")
    if lobby["invite_status"] != "pending":
        raise HTTPException(status_code=400, detail="Esta invitacion ya fue gestionada.")

    await database.execute(
        """
        UPDATE lobby_invites
        SET status = 'accepted'
        WHERE lobby_id = :id AND (invited_id = :uid OR invited_user_id = :uid)
        """,
        {"id": int(game_id), "uid": current_user["id"]},
    )

    _, game = await get_game_or_create_from_lobby(int(game_id))
    game.setdefault("players_ready", {})
    game["players_ready"][current_user["username"]] = False

    await notifier.send_invite_response(
        target_username=lobby["creator_username"],
        game_id=game_id,
        action="accepted",
        guest=current_user["username"],
    )

    return {"status": "success", "game_id": game_id}


@router.post("/{game_id}/reject")
async def reject_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_lobby_invites_table()

    lobby = await database.fetch_one(
        """
        SELECT l.id, l.creator_id, cu.username AS creator_username, li.status AS invite_status
        FROM lobbies l
        JOIN users cu ON cu.id = l.creator_id
        JOIN lobby_invites li ON li.lobby_id = l.id AND COALESCE(li.invited_id, li.invited_user_id) = :uid
        WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false
        """,
        {"id": int(game_id), "uid": current_user["id"]},
    )
    if not lobby:
        raise HTTPException(status_code=400, detail="La invitacion no existe.")
    if lobby["invite_status"] != "pending":
        raise HTTPException(status_code=400, detail="Esta invitacion ya fue gestionada.")

    participants = await get_lobby_participants(int(game_id))
    usernames_to_notify = [p["username"] for p in participants if p["username"] != current_user["username"]]

    await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
    game_manager.remove_game(game_id)

    for username in usernames_to_notify:
        await notifier.send_invite_response(
            target_username=username,
            game_id=game_id,
            action="rejected",
            guest=current_user["username"],
        )

    return {"status": "success"}


@router.post("/{game_id}/leave")
async def leave_lobby(game_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_lobby_invites_table()

    lobby = await database.fetch_one(
        """
        SELECT id, creator_id, mode, status
        FROM lobbies
        WHERE id = :id
        """,
        {"id": int(game_id)},
    )
    if not lobby:
        raise HTTPException(status_code=404, detail="La sala no existe")

    participants = await get_lobby_participants(int(game_id))
    usernames_by_id = {p["user_id"]: p["username"] for p in participants}
    participant_ids = set(usernames_by_id.keys())
    if current_user["id"] not in participant_ids:
        raise HTTPException(status_code=403, detail="No perteneces a esta sala")

    leaving_username = usernames_by_id[current_user["id"]]

    # En sala de espera: si uno se va, se cierra para todos.
    if lobby["status"] == "waiting":
        await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
        game_manager.remove_game(game_id)

        for participant in participants:
            if participant["username"] == leaving_username:
                continue
            await notifier.send_invite_response(
                target_username=participant["username"],
                game_id=game_id,
                action="left",
                guest=leaving_username,
            )

        return {"status": "success"}

    # En partida: abandono individual.
    if current_user["id"] != lobby["creator_id"]:
        await database.execute(
            """
            UPDATE lobby_invites
            SET status = 'left'
            WHERE lobby_id = :id AND (invited_id = :uid OR invited_user_id = :uid)
            """,
            {"id": int(game_id), "uid": current_user["id"]},
        )

    success, message = await game_manager.abandon_game(game_id, leaving_username)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    game = game_manager.get_game_state(game_id)
    if game:
        await ws_manager.broadcast_game_state(game_id, game)
    if game and game.get("game_over"):
        await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})

    return {"status": "success", "message": message}


@router.get("/{game_id}/state")
async def get_lobby_state(game_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_lobby_invites_table()

    lobby = await database.fetch_one(
        """
        SELECT id, creator_id, status, mode
        FROM lobbies
        WHERE id = :id
        """,
        {"id": int(game_id)},
    )
    if not lobby:
        raise HTTPException(status_code=404, detail="Sala no encontrada")

    creator_id = lobby["creator_id"]
    invite_membership = await database.fetch_one(
        """
        SELECT status
        FROM lobby_invites
        WHERE lobby_id = :id AND (invited_id = :uid OR invited_user_id = :uid)
        """,
        {"id": int(game_id), "uid": current_user["id"]},
    )
    if current_user["id"] != creator_id and not invite_membership:
        raise HTTPException(status_code=403, detail="No perteneces a esta sala")

    _, game = await get_game_or_create_from_lobby(int(game_id))
    ready = game.get("players_ready", {}) if game else {}

    creator_row = await database.fetch_one(
        "SELECT id, username, elo, avatar_url FROM users WHERE id = :uid",
        {"uid": creator_id},
    )
    invited_rows = await database.fetch_all(
        """
        SELECT u.id, u.username, u.elo, u.avatar_url, li.status, li.invite_order
        FROM lobby_invites li
        JOIN users u ON u.id = COALESCE(li.invited_id, li.invited_user_id)
        WHERE li.lobby_id = :id AND li.status = 'accepted'
        ORDER BY li.invite_order ASC
        """,
        {"id": int(game_id)},
    )

    players = []
    if creator_row:
        players.append({
            "id": creator_row["id"],
            "username": creator_row["username"],
            "rr": creator_row["elo"],
            "avatar_url": creator_row["avatar_url"],
            "is_ready": bool(ready.get(creator_row["username"], False)),
        })

    for row in invited_rows:
        players.append({
            "id": row["id"],
            "username": row["username"],
            "rr": row["elo"],
            "avatar_url": row["avatar_url"],
            "is_ready": bool(ready.get(row["username"], False)),
        })

    status = game.get("status", lobby["status"]) if game else lobby["status"]
    if status == "finished":
        status = "playing"

    return {
        "game_id": game_id,
        "status": status,
        "mode": lobby["mode"],
        "players": players,
    }


@router.post("/{game_id}/ready")
async def set_ready(game_id: str, body: ReadyRequest, current_user: dict = Depends(get_current_user)):
    await ensure_lobby_invites_table()

    lobby = await database.fetch_one(
        "SELECT id, creator_id, mode FROM lobbies WHERE id = :id",
        {"id": int(game_id)},
    )
    if not lobby:
        raise HTTPException(status_code=404, detail="Sala no encontrada")

    creator_membership = current_user["id"] == lobby["creator_id"]
    invite_membership = await database.fetch_one(
        """
        SELECT status
        FROM lobby_invites
        WHERE lobby_id = :id AND (invited_id = :uid OR invited_user_id = :uid)
        """,
        {"id": int(game_id), "uid": current_user["id"]},
    )
    if not creator_membership and not invite_membership:
        raise HTTPException(status_code=403, detail="No perteneces a esta sala")
    if invite_membership and invite_membership["status"] != "accepted":
        raise HTTPException(status_code=403, detail="Debes aceptar la invitacion antes de marcarte listo")

    _, game = await get_game_or_create_from_lobby(int(game_id))
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
