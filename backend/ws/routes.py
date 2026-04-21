import html
import asyncio
import json
import time
import os
from typing import List, Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ai.engine import get_best_ai_move, get_best_ai_move_4p, get_ai_skill_action
from auth.dependencies import verify_token_ws
from game.manager import TURN_ORDER_4P, game_manager
from persistence.database import database
from rules.logic import count_score, count_score_4p, get_valid_moves, get_valid_moves_4p
from ws.manager import manager
from ws.notifications import notifier

router = APIRouter()
WAITING_ROOM_DISCONNECT_GRACE_SECONDS = float(
    os.getenv("WAITING_ROOM_DISCONNECT_GRACE_SECONDS", "3")
)

def mode_to_api(mode: str) -> str:
    has_skills = "_skills" in mode
    base = mode.replace("_skills", "")
    suffix = "_skills" if has_skills else ""
    if base == "1v1": return "1vs1" + suffix
    if base in ("1v1v1v1", "1vs1vs1vs1"): return "1vs1vs1vs1" + suffix
    return mode

async def get_room_players(game: dict) -> List[dict]:
    parts = [u for u in game.get("participants", []) if u]
    if not parts:
        return []

    human_parts = [u for u in parts if not u.startswith("IA")]
    rows = await database.fetch_all(
        "SELECT id, username, elo, avatar_url FROM users WHERE username = ANY(:uns)",
        {"uns": human_parts},
    ) if human_parts else []
    by_un = {r["username"]: r for r in rows}

    room_players = []
    for username in parts:
        if username.startswith("IA"):
            room_players.append({
                "id": -1,
                "username": username,
                "rr": 1000,
                "avatar_url": "",
                "is_ready": True,
            })
            continue
        if username in by_un:
            room_players.append({
                "id": by_un[username]["id"],
                "username": by_un[username]["username"],
                "rr": by_un[username]["elo"],
                "avatar_url": by_un[username]["avatar_url"],
                "is_ready": bool(game.get("players_ready", {}).get(username, False)),
            })
    return room_players

async def broadcast_room_sync(game_id: str):
    game = game_manager.get_game_state(game_id)
    if game:
        await manager.broadcast(game_id, {
            "type": "room_sync", 
            "payload": {"game_id": game_id, "status": game.get("status", "waiting"), "mode": mode_to_api(game.get("mode", "1v1")), "players": await get_room_players(game)}
        })

def ensure_user_assigned_to_game(game: dict, username: str) -> Optional[str]:
    if game.get("mode") in ("1v1v1v1", "1v1v1v1_skills"):
        piece = game.get("piece_by_username", {}).get(username)
        if piece: return piece
        if username in game.get("participants", []):
            for np in TURN_ORDER_4P:
                if not game.get("username_by_piece", {}).get(np):
                    game["username_by_piece"][np] = username
                    game["piece_by_username"][username] = np
                    if np not in game.get("active_pieces", []): game["active_pieces"].append(np)
                    game.setdefault("players_ready", {})[username] = False
                    return np
        if len(game.get("participants", [])) >= game.get("participant_count_expected", 4): return None
        game.setdefault("participants", []).append(username)
        game.setdefault("players_ready", {})[username] = False
        for np in TURN_ORDER_4P:
            if not game.get("username_by_piece", {}).get(np):
                game["username_by_piece"][np] = username
                game["piece_by_username"][username] = np
                if np not in game.get("active_pieces", []): game["active_pieces"].append(np)
                return np
        return None

    if game.get("black_player") == username: return "black"
    if game.get("white_player") == username: return "white"
    if not game.get("black_player"):
        game["black_player"] = username
        game.setdefault("participants", []).append(username)
        game.setdefault("players_ready", {})[username] = False
        return "black"
    if not game.get("white_player"):
        game["white_player"] = username
        game.setdefault("participants", []).append(username)
        game.setdefault("players_ready", {})[username] = False
        return "white"
    return None

def schedule_room_cleanup(g_id: str, delay: int = 5):
    async def cleanup_task():
        await asyncio.sleep(delay)
        game_manager.remove_game(g_id)
    asyncio.create_task(cleanup_task())

@router.websocket("/play/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, token: str = Query(...)):
    if not game_id.isdigit():
        await websocket.accept(); await websocket.close(code=1008, reason="ID invalido"); return

    user = await verify_token_ws(token)
    if not user:
        await websocket.accept(); await websocket.close(code=1008, reason="Token invalido"); return

    username = user["username"]
    game = game_manager.get_game_state(game_id)
    if not game:
        await websocket.accept(); await websocket.send_json({"error": "Sala no encontrada"}); await websocket.close(); return

    assigned_piece = ensure_user_assigned_to_game(game, username)
    if not assigned_piece:
        await websocket.accept(); await websocket.send_json({"type": "error", "payload": {"message": "La sala esta llena"}}); await websocket.close(); return

    connected = await manager.connect(websocket, game_id, username)
    if not connected:
        return
        
    timer_key = f"{game_id}_{username}"
    if timer_key in manager.disconnect_timers:
        manager.disconnect_timers[timer_key].cancel()
        del manager.disconnect_timers[timer_key]

    try:
        was_paused = username in game.get("paused_usernames", [])
        if was_paused:
            game_manager.resume_player(game_id, username)
            await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))

        await websocket.send_json({"type": "player_assignment", "payload": {"color": assigned_piece}})
        game.setdefault("players_ready", {})[username] = False

        if game.get("mode", "").replace("_skills", "") == "vs_ai":
            game_manager.set_game_playing(game_id)
            await websocket.send_json({
                "type": "game_state_update",
                "payload": game_manager.get_game_state(game_id)
            })
        else:
            await broadcast_room_sync(game_id)
        if game.get("status") == "waiting":
            await websocket.send_json({"type": "waiting_for_player", "payload": {"message": "Esperando a que todos esten listos..."}})
        else:
            await websocket.send_json({
                "type": "game_state_update",
                "payload": game_manager.get_game_state(game_id)
            })

        last_chat_time: float = 0.0

        def check_and_trigger_ai(current_state):
            if not current_state or current_state.get("game_over"): return

            c_player = current_state.get("current_player")
            g_mode = current_state.get("mode", "")
            base_g_mode = g_mode.replace("_skills", "")

            is_1v1_ai = (base_g_mode == "vs_ai" and c_player == "white")
            u_name = current_state.get("username_by_piece", {}).get(c_player)
            is_4p_ai = (base_g_mode in ("1v1v1v1", "1vs1vs1vs1") and u_name and u_name.startswith("IA_"))

            if is_1v1_ai or is_4p_ai:
                async def play_ai_turn():
                    await asyncio.sleep(0.5)
                    current = game_manager.get_game_state(game_id)
                    if not current or current.get("game_over"): return
                    if current.get("paused_usernames"): return

                    # Intentar usar habilidad si la IA tiene en inventario
                    ai_skill_action = get_ai_skill_action(current, c_player)
                    if ai_skill_action:
                        skill_success, _ = await game_manager.use_skill(game_id, c_player, ai_skill_action)
                        if skill_success:
                            ais = game_manager.get_game_state(game_id)
                            if ais and ais.get("game_over"):
                                await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                                schedule_room_cleanup(game_id)
                            await manager.broadcast_game_state(game_id, ais)
                            check_and_trigger_ai(ais)
                            return

                    # Sin habilidades usables: movimiento normal
                    fixed_set_ai = {tuple(p) for p in current.get("fixed_pieces", [])}
                    if is_4p_ai:
                        ai_move = await asyncio.to_thread(get_best_ai_move_4p, current["board"], c_player, fixed_set_ai)
                        r, c = (ai_move["row"], ai_move["col"]) if ai_move else (None, None)
                    else:
                        ai_move = await asyncio.to_thread(get_best_ai_move, current["board"], c_player, fixed_set_ai)
                        r, c = (ai_move.row, ai_move.col) if ai_move else (None, None)

                    if r is not None and c is not None:
                        ai_success, _ = await game_manager.make_move(game_id, c_player, r, c)
                        if ai_success:
                            ais = game_manager.get_game_state(game_id)
                            if ais and ais.get("game_over"):
                                await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                                schedule_room_cleanup(game_id)
                            await manager.broadcast_game_state(game_id, ais)
                            check_and_trigger_ai(ais)

                asyncio.create_task(play_ai_turn())

        while True:
            data = await websocket.receive_text()
            
            # PROTECCION ANTI-BASURA DE RED
            try: message = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                await manager.send_error(websocket, "Formato invalido")
                continue

            action = message.get("action")

            # ACCION DE DEBUG PARA LOS TESTS AUTOMATICOS
            if action == "debug_force_state":
                game["board"] = message.get("board")
                game["current_player"] = message.get("current_player")
                if "fixed_pieces" in message:
                    game["fixed_pieces"] = message.get("fixed_pieces", [])
                if "skills_inventory" in message:
                    game["skills_inventory"] = message.get("skills_inventory", {})

                fixed_set = {tuple(p) for p in game.get("fixed_pieces", [])}
                mode = game.get("mode", "")
                if mode.replace("_skills", "") in ("1v1v1v1", "1vs1vs1vs1"):
                    game["score"] = count_score_4p(game["board"])
                    current_piece = game.get("current_player")
                    if current_piece:
                        game["valid_moves"] = get_valid_moves_4p(game["board"], current_piece, fixed_set)
                    else:
                        game["valid_moves"] = []
                else:
                    game["score"] = count_score(game["board"])
                    current_piece = game.get("current_player")
                    if current_piece in ("black", "white"):
                        game["valid_moves"] = [m.dict() for m in get_valid_moves(game["board"], current_piece, fixed_set)]
                    else:
                        game["valid_moves"] = []
                await manager.broadcast_game_state(game_id, game)
                check_and_trigger_ai(game)
                continue
            if action == "debug_give_skill":
                target_player = message.get("player")
                skill_to_give = message.get("skill")
                game.setdefault("skills_inventory", {}).setdefault(target_player, []).append(skill_to_give)
                await manager.broadcast_game_state(game_id, game)
                check_and_trigger_ai(game)
                continue

            if action == "set_ready":
                game_manager.set_player_ready(game_id, username, bool(message.get("ready")))
                await broadcast_room_sync(game_id)
                if game_manager.are_all_players_ready(game_id):
                    game_manager.set_game_playing(game_id)
                    await database.execute("UPDATE lobbies SET status = 'playing' WHERE id = :id", {"id": int(game_id)})
                    await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))
                continue

            if action == "chat":
                # ANTI-SPAM (maximo un mensaje cada 0.5s)
                now = time.monotonic()
                if now - last_chat_time < 0.5:
                    continue  # Ignorar spam de chat
                last_chat_time = now

                raw_msg = str(message.get("message", ""))[:280]
                msg_txt = html.escape(raw_msg)
                if msg_txt.strip():
                    await manager.broadcast(game_id, {"type": "chat_message", "payload": {"sender": username, "message": msg_txt}})
                continue

            if action == "pause":
                success, msg = game_manager.pause_player(game_id, username)
                if success:
                    await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))
                else:
                    await manager.send_error(websocket, msg)
                continue

            if action == "surrender":
                if game.get("mode", "").replace("_skills", "") == "vs_ai":
                    success, msg = await game_manager.surrender_game(game_id, assigned_piece)
                else:
                    # En partidas online tratamos "abandonar" como abandono real
                    success, msg = await game_manager.abandon_game(game_id, username)
                if success:
                    ns = game_manager.get_game_state(game_id)
                    if ns and ns.get("game_over"): 
                        await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                        schedule_room_cleanup(game_id)
                    await manager.broadcast_game_state(game_id, ns)
                else: await manager.send_error(websocket, msg)
                continue

            if action == "make_move":
                row = message.get("row")
                col = message.get("col")
                
                if not isinstance(row, int) or not isinstance(col, int):
                    await manager.send_error(websocket, "Formato de coordenadas invalido (deben ser numeros)")
                    continue
                
                mode = game.get("mode", "1v1")
                max_size = 16 if mode.replace("_skills", "") in ("1v1v1v1", "1vs1vs1vs1") else 8
                if row < 0 or row >= max_size or col < 0 or col >= max_size:
                    await manager.send_error(websocket, "Coordenadas fuera del tablero")
                    continue

                success, msg = await game_manager.make_move(game_id, assigned_piece, message.get("row"), message.get("col"))
                if success:
                    ns = game_manager.get_game_state(game_id)
                    if ns and ns.get("game_over"): 
                        await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                        schedule_room_cleanup(game_id)
                    await manager.broadcast_game_state(game_id, ns)
                    check_and_trigger_ai(ns)
                    
                else: await manager.send_error(websocket, msg)
                continue

            if action == "use_skill":
                success, msg = await game_manager.use_skill(game_id, assigned_piece, message)
                if success:
                    ns = game_manager.get_game_state(game_id)
                    if ns and ns.get("game_over"):
                        await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                        schedule_room_cleanup(game_id)
                    await manager.broadcast_game_state(game_id, ns)
                    check_and_trigger_ai(ns)
                else:
                    await manager.send_error(websocket, msg)
                continue

    except Exception as e:
        manager.disconnect(websocket, game_id, username)
        if not (game := game_manager.get_game_state(game_id)): return

        if game.get("status") == "waiting":
            async def waiting_disconnect_task():
                try:
                    # Evita cerrar la sala por desconexiones fugaces (re-render, microcortes, etc.)
                    await asyncio.sleep(WAITING_ROOM_DISCONNECT_GRACE_SECONDS)
                    latest_game = game_manager.get_game_state(game_id)
                    if not latest_game or latest_game.get("status") != "waiting":
                        return

                    lobby = await database.fetch_one(
                        "SELECT creator_id, is_public, id FROM lobbies WHERE id = :id",
                        {"id": int(game_id)}
                    )
                    is_host = lobby and int(lobby["creator_id"]) == int(user["id"])

                    rival_asignado = bool(
                        latest_game.get("white_player") or
                        latest_game.get("black_player") and latest_game.get("black_player") != username
                    )

                    if is_host and not rival_asignado:
                        await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
                        game_manager.remove_game(game_id)
                        await manager.broadcast(game_id, {"type": "error", "payload": {"message": "El host ha abandonado la sala. Partida cancelada."}})

                        parts = latest_game.get("participants", [])
                        for p in parts:
                            if p != username:
                                await notifier.send_invite_response(target_username=p, game_id=game_id, action="room_closed", guest=username)
                    else:
                        tiene_pieza = (
                            latest_game.get("black_player") == username or
                            latest_game.get("white_player") == username or
                            username in latest_game.get("piece_by_username", {})
                        )
                        if username in latest_game.get("participants", []) and not tiene_pieza:
                            latest_game["participants"].remove(username)
                            latest_game.get("players_ready", {}).pop(username, None)
                            await database.execute(
                                "DELETE FROM lobby_invites WHERE lobby_id = :id AND invited_user_id = :uid",
                                {"id": int(game_id), "uid": user["id"]}
                            )

                        await broadcast_room_sync(game_id)
                        parts = latest_game.get("participants", [])
                        for p in parts:
                            if p != username:
                                await notifier.send_invite_response(target_username=p, game_id=game_id, action="left", guest=username)
                except asyncio.CancelledError:
                    pass
                finally:
                    if timer_key in manager.disconnect_timers:
                        del manager.disconnect_timers[timer_key]

            if timer_key in manager.disconnect_timers:
                manager.disconnect_timers[timer_key].cancel()
            manager.disconnect_timers[timer_key] = asyncio.create_task(waiting_disconnect_task())
            return

        if game.get("status") == "playing" and not game.get("game_over"):
            if username in game.get("paused_usernames", []):
                return

            async def abandonment_task():
                try:
                    await asyncio.sleep(30)
                    suc, _ = await game_manager.abandon_game(game_id, username)
                    if suc:
                        ns = game_manager.get_game_state(game_id)
                        if ns and ns.get("game_over"): 
                            await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                            schedule_room_cleanup(game_id)
                        await manager.broadcast_game_state(game_id, ns)
                except asyncio.CancelledError: 
                        pass
                finally:
                    if timer_key in manager.disconnect_timers:
                        del manager.disconnect_timers[timer_key]
            manager.disconnect_timers[timer_key] = asyncio.create_task(abandonment_task())

@router.websocket("/notifications")
async def notifications_endpoint(websocket: WebSocket, token: str = Query(...)):
    user = await verify_token_ws(token)
    if not user:
        await websocket.accept(); await websocket.close(code=1008, reason="Token invalido"); return
    un = user["username"]
    await notifier.connect(websocket, un)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: notifier.disconnect(un)
