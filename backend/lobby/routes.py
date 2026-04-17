import asyncio
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
    has_skills = "_skills" in mode
    base = mode.replace("_skills", "")
    if base in ("1vs1vs1vs1", "1v1v1v1"):
        result = "1v1v1v1"
    elif base == "vs_ai":
        result = "vs_ai"
    else:
        result = "1v1"
    return result + ("_skills" if has_skills else "")

async def get_lobby_participants(lobby_id: int) -> List[Dict]:
    lobby = await database.fetch_one("SELECT l.id, l.creator_id, cu.username AS creator_username FROM lobbies l JOIN users cu ON cu.id = l.creator_id WHERE l.id = :id", {"id": lobby_id})
    if not lobby: return []

    invited_rows = await database.fetch_all(
        """
        SELECT li.invited_user_id, li.status, li.invite_order, u.username
        FROM lobby_invites li JOIN users u ON u.id = li.invited_user_id
        WHERE li.lobby_id = :id AND li.status = 'accepted' ORDER BY li.invite_order ASC
        """, {"id": lobby_id}
    )

    parts = [{"user_id": lobby["creator_id"], "username": lobby["creator_username"], "status": "accepted", "invite_order": 0, "is_creator": True}]
    for r in invited_rows:
        parts.append({"user_id": r["invited_user_id"], "username": r["username"], "status": r["status"], "invite_order": int(r["invite_order"]) + 1, "is_creator": False})
    return parts

async def get_game_or_create_from_lobby(lobby_id: int) -> Tuple[dict, dict]:
    lobby = await database.fetch_one("SELECT id, creator_id, mode, status, is_public FROM lobbies WHERE id = :id", {"id": lobby_id})
    if not lobby: raise HTTPException(status_code=404, detail="Sala no encontrada")

    game_id = str(lobby_id)
    game = game_manager.get_game_state(game_id)
    if game: return lobby, game

    parts = await get_lobby_participants(lobby_id)
    ordered = [p["username"] for p in sorted(parts, key=lambda p: p["invite_order"])]
    game_manager.create_game(
        creator_name=ordered[0],
        game_id=game_id,
        mode=normalize_mode(lobby["mode"]),
        participants=ordered,
        is_private=not bool(lobby["is_public"]),
    )
    return lobby, game_manager.get_game_state(game_id)

@router.post("/create")
async def create_public_lobby(req: GameCreateRequest, current_user: dict = Depends(get_current_user)):
    base_mode = req.mode.replace("_skills", "")
    is_public = base_mode in ("1vs1", "1v1", "1vs1vs1vs1", "1v1v1v1")
    lobby_id = await database.fetch_val("INSERT INTO lobbies (creator_id, is_public, status, mode) VALUES (:cid, :pub, 'waiting', :m) RETURNING id",
        {"cid": current_user["id"], "pub": is_public, "m": req.mode})
    
    game_id = str(lobby_id)
    game_manager.create_game(creator_name=current_user["username"], game_id=game_id, mode=normalize_mode(req.mode), participants=[current_user["username"]])
    return {"game_id": game_id, "creator": current_user["username"], "mode": req.mode}

@router.get("/public")
async def get_public_lobbies():
    rows = await database.fetch_all("SELECT l.id AS game_id, u.username AS creator, u.avatar_url, u.elo AS creator_rr, l.mode FROM lobbies l JOIN users u ON l.creator_id = u.id WHERE l.status = 'waiting' AND l.is_public = true")
    lobbies = []
    for r in rows:
        g_id = str(r["game_id"])
        if g_id not in game_manager.active_games:
            game_manager.create_game(creator_name=r["creator"], game_id=g_id, mode=normalize_mode(r["mode"]), participants=[r["creator"]])
        game = game_manager.get_game_state(g_id) or {}
        participants = game.get("participants", [])
        expected = game.get("participant_count_expected", 4 if normalize_mode(r["mode"]).replace("_skills", "") == "1v1v1v1" else 2)
        lobbies.append({
            "game_id": g_id,
            "creator": r["creator"],
            "avatar_url": r["avatar_url"],
            "creator_rr": r["creator_rr"],
            "mode": r["mode"],
            "players": len(participants),
            "max_players": expected,
            "status": game.get("status", "waiting")
        })
    return {"lobbies": lobbies}

@router.post("/join/{game_id}")
async def join_public_lobby(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT id, mode, status FROM lobbies WHERE id = :id AND is_public = true", {"id": int(game_id)})
    if not lobby or lobby["status"] != "waiting":
        raise HTTPException(status_code=400, detail="La sala ya esta llena o no existe.")

    game = game_manager.get_game_state(game_id)
    if not game:
        raise HTTPException(status_code=400, detail="La sala ya esta llena o no existe.")

    expected = game.get("participant_count_expected", 2)
    parts = game.setdefault("participants", [])

    if current_user["username"] not in parts:
        if len(parts) >= expected:
            raise HTTPException(status_code=400, detail="La sala ya esta llena.")
        parts.append(current_user["username"])
        game.setdefault("players_ready", {})[current_user["username"]] = False

    # Legado 1v1: Si es una partida de 2 y acaba de entrar el segundo, le asignamos blancas explícitamente
    if expected == 2 and len(parts) == 2 and not game.get("white_player"):
        game["white_player"] = current_user["username"]

    # Si la sala acaba de llenarse, marcarla como playing para que desaparezca del lobby público
    if len(parts) >= expected:
        await database.execute("UPDATE lobbies SET status = 'playing' WHERE id = :id", {"id": int(game_id)})

    return {"status": "success", "game_id": game_id}

@router.post("/invite")
async def invite_friend(req: GameInviteRequest, current_user: dict = Depends(get_current_user)):
    mode = req.mode if req.mode in ("1vs1", "1vs1vs1vs1") else "1vs1"
    expected = 1 if mode == "1vs1" else 3
    friend_ids = list(dict.fromkeys(req.friend_ids))
    if len(friend_ids) != expected: raise HTTPException(status_code=400, detail=f"Requiere {expected} invitacion(es).")
    if current_user["id"] in friend_ids: raise HTTPException(status_code=400, detail="No puedes invitarte a ti")

    friends = {r["id"]: r for r in await database.fetch_all("SELECT id, username FROM users WHERE id = ANY(:ids)", {"ids": friend_ids})}
    if len(friends) != len(friend_ids): raise HTTPException(status_code=404, detail="Amigo no encontrado")

    for fid in friend_ids:
        friendship = await database.fetch_one("SELECT 1 FROM friendships WHERE status = 'accepted' AND ((user_id = :uid AND friend_id = :fid) OR (user_id = :fid AND friend_id = :uid))", {"uid": current_user["id"], "fid": fid})
        if not friendship: raise HTTPException(status_code=403, detail="Solo puedes invitar amigos")

    lobby_id = await database.fetch_val("INSERT INTO lobbies (creator_id, is_public, status, mode) VALUES (:cid, false, 'waiting', :m) RETURNING id", {"cid": current_user["id"], "m": mode})
    game_id = str(lobby_id)

    for i, fid in enumerate(friend_ids):
        await database.execute("INSERT INTO lobby_invites (lobby_id, invited_user_id, invite_order, status) VALUES (:lid, :fid, :io, 'pending')", {"lid": lobby_id, "fid": fid, "io": i})

    game_manager.create_game(creator_name=current_user["username"], is_private=True, game_id=game_id, mode=normalize_mode(mode), participants=[current_user["username"]])
    
    sent_count = 0
    for fid in friend_ids:
        if await notifier.send_invite(target_username=friends[fid]["username"], creator=current_user["username"], game_id=game_id, mode=mode):
            sent_count += 1
    return {"game_id": game_id, "creator": current_user["username"], "mode": mode, "invites_sent": sent_count}

@router.post("/{game_id}/accept")
async def accept_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT l.id, l.creator_id, cu.username AS creator_username, li.status AS invite_status FROM lobbies l JOIN users cu ON cu.id = l.creator_id JOIN lobby_invites li ON li.lobby_id = l.id AND li.invited_user_id = :uid WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false", {"id": int(game_id), "uid": current_user["id"]})
    if not lobby: raise HTTPException(status_code=400, detail="Invitacion no disponible.")
    if lobby["invite_status"] != "pending": raise HTTPException(status_code=400, detail="Invitacion gestionada.")

    await database.execute("UPDATE lobby_invites SET status = 'accepted' WHERE lobby_id = :id AND invited_user_id = :uid", {"id": int(game_id), "uid": current_user["id"]})
    _, game = await get_game_or_create_from_lobby(int(game_id))
    game.setdefault("players_ready", {})[current_user["username"]] = False
    await notifier.send_invite_response(target_username=lobby["creator_username"], game_id=game_id, action="accepted", guest=current_user["username"])
    return {"status": "success", "game_id": game_id}

@router.post("/{game_id}/reject")
async def reject_invite(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT l.id, l.creator_id, cu.username AS creator_username, li.status AS invite_status, l.mode FROM lobbies l JOIN users cu ON cu.id = l.creator_id JOIN lobby_invites li ON li.lobby_id = l.id AND li.invited_user_id = :uid WHERE l.id = :id AND l.status = 'waiting' AND l.is_public = false", {"id": int(game_id), "uid": current_user["id"]})
    if not lobby: raise HTTPException(status_code=400, detail="Invitacion no disponible.")
    
    await database.execute("UPDATE lobby_invites SET status = 'rejected' WHERE lobby_id = :id AND invited_user_id = :uid", {"id": int(game_id), "uid": current_user["id"]})
    
    if lobby["mode"] in ("1vs1", "1v1"):
        parts = await get_lobby_participants(int(game_id))
        await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
        game_manager.remove_game(game_id)
        for un in [p["username"] for p in parts if p["username"] != current_user["username"]]:
            await notifier.send_invite_response(target_username=un, game_id=game_id, action="room_closed", guest=current_user["username"])
    else:
        # En 4P, solo avisamos al host y no destruimos la sala
        await notifier.send_invite_response(target_username=lobby["creator_username"], game_id=game_id, action="rejected", guest=current_user["username"])
        
    return {"status": "success"}

@router.post("/{game_id}/leave")
async def leave_lobby(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT id, creator_id, status, mode, is_public FROM lobbies WHERE id = :id", {"id": int(game_id)})
    if not lobby: raise HTTPException(status_code=404, detail="Sala no existe")

    game = game_manager.get_game_state(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Partida no encontrada")

    parts_usernames = game.get("participants", [])
    username = current_user["username"]
    if username not in parts_usernames:
        raise HTTPException(status_code=403, detail="No perteneces a sala")
    
    if lobby["status"] == "waiting":
        # Solo destruir la sala si el que se va es el creador (Host).
        # Si se va un invitado, la sala sigue abierta para que el host espere a otro.
        creator_id = int(lobby["creator_id"])
        user_id = int(current_user["id"])
        should_destroy_room = user_id == creator_id
        print(f"LOBBY DEBUG: User {username} (ID {user_id}) leaves room {game_id}. Creator ID is {creator_id}. Should destroy? {should_destroy_room}")
        
        if should_destroy_room:
            await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
            game_manager.remove_game(game_id)
            for p in parts_usernames:
                if p != username:
                    await notifier.send_invite_response(target_username=p, game_id=game_id, action="room_closed", guest=username)
            return {"status": "success", "message": "Has abandonado la sala y la partida se ha cancelado"}
        else:
            # Si se va un guest, simplemente liberamos su hueco.
            await database.execute("DELETE FROM lobby_invites WHERE lobby_id = :id AND invited_user_id = :uid", {"id": int(game_id), "uid": current_user["id"]})
            
            if username in game.get("participants", []):
                game["participants"].remove(username)
                game.get("players_ready", {}).pop(username, None)
            
            creator_name = await database.fetch_val("SELECT username FROM users WHERE id = :uid", {"uid": lobby["creator_id"]})
            if creator_name:
                await notifier.send_invite_response(target_username=creator_name, game_id=game_id, action="left", guest=username)
            await ws_manager.broadcast_game_state(game_id, game)
            return {"status": "success", "message": "Has abandonado la sala"}

    if current_user["id"] != lobby["creator_id"]:
        await database.execute("UPDATE lobby_invites SET status = 'left' WHERE lobby_id = :id AND invited_user_id = :uid", {"id": int(game_id), "uid": current_user["id"]})
    
    success, msg = await game_manager.abandon_game(game_id, username)
    if not success: raise HTTPException(status_code=400, detail=msg)
    
    game = game_manager.get_game_state(game_id)
    if game: await ws_manager.broadcast_game_state(game_id, game)
    if game and game.get("game_over"): await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
    return {"status": "success", "message": msg}

@router.get("/{game_id}/state")
async def get_lobby_state(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT id, creator_id, status, mode FROM lobbies WHERE id = :id", {"id": int(game_id)})
    if not lobby: raise HTTPException(status_code=404, detail="Sala no encontrada")

    _, game = await get_game_or_create_from_lobby(int(game_id))
    if current_user["username"] not in game.get("participants", []):
        raise HTTPException(status_code=403, detail="No perteneces a la sala")

    ready = game.get("players_ready", {}) if game else {}
    parts_usernames = game.get("participants", [])

    players = []
    if parts_usernames:
        db_users = await database.fetch_all("SELECT id, username, elo, avatar_url FROM users WHERE username = ANY(:usernames)", {"usernames": parts_usernames})
        user_map = {u["username"]: {"id": u["id"], "rr": u["elo"], "avatar_url": u["avatar_url"]} for u in db_users}
        for uname in parts_usernames:
            if uname.startswith("IA_"):
                players.append({"id": -1, "username": uname, "rr": 1000, "avatar_url": "", "is_ready": True})
            elif uname in user_map:
                u = user_map[uname]
                players.append({"id": u["id"], "username": uname, "rr": u["rr"], "avatar_url": u["avatar_url"], "is_ready": bool(ready.get(uname, False))})

    st = game.get("status", lobby["status"]) if game else lobby["status"]
    return {"game_id": game_id, "status": "playing" if st == "finished" else st, "mode": lobby["mode"], "players": players}

@router.post("/{game_id}/ready")
async def set_ready(game_id: str, body: ReadyRequest, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT id, creator_id FROM lobbies WHERE id = :id", {"id": int(game_id)})
    if not lobby: raise HTTPException(status_code=404, detail="Sala no encontrada")
    
    _, game = await get_game_or_create_from_lobby(int(game_id))
    if current_user["username"] not in game.get("participants", []):
        raise HTTPException(status_code=403, detail="No perteneces a la sala")
    game_manager.set_player_ready(game_id, current_user["username"], body.ready)
    if game_manager.are_all_players_ready(game_id):
        game_manager.set_game_playing(game_id)
        await database.execute("UPDATE lobbies SET status = 'playing' WHERE id = :id", {"id": int(game_id)})
    return {"status": "success", "ready": body.ready, "game_status": game_manager.get_game_state(game_id).get("status", "waiting")}

@router.post("/{game_id}/kick/{username_to_kick}")
async def kick_player(game_id: str, username_to_kick: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT id, creator_id FROM lobbies WHERE id = :id", {"id": int(game_id)})
    if not lobby: raise HTTPException(status_code=404, detail="Sala no encontrada")
    if current_user["id"] != lobby["creator_id"]: raise HTTPException(status_code=403, detail="Solo el creador puede expulsar")
    if current_user["username"] == username_to_kick: raise HTTPException(status_code=400, detail="No puedes expulsarte a ti mismo")

    game = game_manager.get_game_state(game_id)
    if not game or game["status"] != "waiting": raise HTTPException(status_code=400, detail="Partida ya iniciada o no existe")

    parts = game.get("participants", [])
    if username_to_kick not in parts: raise HTTPException(status_code=404, detail="Jugador no esta en la sala")

    # Sacarlo del manager
    parts.remove(username_to_kick)
    game.get("players_ready", {}).pop(username_to_kick, None)

    # Borrar la invitación si la había
    uid_to_kick = await database.fetch_val("SELECT id FROM users WHERE username = :un", {"un": username_to_kick})
    if uid_to_kick:
        await database.execute("DELETE FROM lobby_invites WHERE lobby_id = :id AND invited_user_id = :uid", {"id": int(game_id), "uid": uid_to_kick})

    await notifier.send_invite_response(target_username=username_to_kick, game_id=game_id, action="kicked", guest=current_user["username"])
    # Notificamos por WebSocket al resto para que se refresque el lobby
    await ws_manager.broadcast_game_state(game_id, game)
    return {"status": "success", "message": f"{username_to_kick} expulsado"}

@router.post("/{game_id}/add_bot")
async def add_bot(game_id: str, current_user: dict = Depends(get_current_user)):
    lobby = await database.fetch_one("SELECT id, creator_id FROM lobbies WHERE id = :id", {"id": int(game_id)})
    if not lobby: raise HTTPException(status_code=404, detail="Sala no encontrada")
    if current_user["id"] != lobby["creator_id"]: raise HTTPException(status_code=403, detail="Solo el creador puede añadir bots")
    
    game = game_manager.get_game_state(game_id)
    if not game or game["status"] != "waiting": raise HTTPException(status_code=400, detail="No se puede añadir bots ahora")
    
    expected = game.get("participant_count_expected", 2)
    parts = game.setdefault("participants", [])
    if len(parts) >= expected: raise HTTPException(status_code=400, detail="La sala ya esta llena")
    
    # Asignar IA
    bot_num = 1
    while f"IA_{bot_num}" in parts:
        bot_num += 1
    bot_name = f"IA_{bot_num}"
    parts.append(bot_name)
    game.setdefault("players_ready", {})[bot_name] = True
    
    if len(parts) >= expected:
        await database.execute("UPDATE lobbies SET status = 'playing' WHERE id = :id", {"id": int(game_id)})
        game_manager.set_game_playing(game_id)
    elif game_manager.are_all_players_ready(game_id):
        game_manager.set_game_playing(game_id)
        
    await ws_manager.broadcast_game_state(game_id, game)
    return {"status": "success", "bot_name": bot_name}
