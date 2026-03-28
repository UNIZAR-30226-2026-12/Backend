import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from game.manager import game_manager
from ws.manager import manager
from ws.notifications import notifier
from auth.dependencies import verify_token_ws
from ai.engine import get_best_ai_move
from persistence.database import database

router = APIRouter()


async def broadcast_room_sync(game_id: str):
    game = game_manager.get_game_state(game_id)
    if not game:
        return

    usernames = [u for u in [game.get("black_player"), game.get("white_player")] if u and u != "IA"]
    players = []
    if usernames:
        rows = await database.fetch_all(
            """
            SELECT id, username, elo, avatar_url
            FROM users
            WHERE username = ANY(:usernames)
            """,
            {"usernames": usernames},
        )
        by_name = {r["username"]: r for r in rows}
        ready_map = game.get("players_ready", {})
        for username in usernames:
            row = by_name.get(username)
            if not row:
                continue
            players.append({
                "id": row["id"],
                "username": row["username"],
                "rr": row["elo"],
                "avatar_url": row["avatar_url"],
                "is_ready": bool(ready_map.get(username, False)),
            })

    await manager.broadcast(game_id, {
        "type": "room_sync",
        "payload": {
            "game_id": game_id,
            "status": game.get("status", "waiting"),
            "mode": "1vs1" if game.get("mode") == "1v1" else game.get("mode"),
            "players": players,
        },
    })


@router.websocket("/play/{game_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    token: str = Query(...),
):
    user = await verify_token_ws(token)
    if not user:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido")
        return

    username = user["username"]
    game = game_manager.get_game_state(game_id)
    if not game:
        await websocket.accept()
        await websocket.send_json({"error": "Sala no encontrada"})
        await websocket.close()
        return

    await manager.connect(websocket, game_id)

    timer_key = f"{game_id}_{username}"
    if timer_key in manager.disconnect_timers:
        manager.disconnect_timers[timer_key].cancel()
        del manager.disconnect_timers[timer_key]

    if game.get("black_player") == username:
        mi_color = "black"
    elif game.get("white_player") == username:
        mi_color = "white"
    else:
        if not game.get("black_player"):
            game["black_player"] = username
            mi_color = "black"
        elif not game.get("white_player"):
            game["white_player"] = username
            mi_color = "white"
        else:
            await websocket.send_json({"type": "error", "payload": {"message": "La sala está llena"}})
            await websocket.close()
            return

    game.setdefault("players_ready", {})
    game["players_ready"].setdefault(username, False)
    await websocket.send_json({"type": "player_assignment", "payload": {"color": mi_color}})

    if game["mode"] == "vs_ai":
        game_manager.set_game_playing(game_id)
        current_state = game_manager.get_game_state(game_id)
        await manager.broadcast_game_state(game_id, current_state)
    else:
        await broadcast_room_sync(game_id)
        if game["status"] == "waiting":
            await websocket.send_json({"type": "waiting_for_player", "payload": {"message": "Esperando a que ambos estén listos..."}})
        else:
            current_state = game_manager.get_game_state(game_id)
            await manager.broadcast_game_state(game_id, current_state)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                await manager.send_error(websocket, "Formato de mensaje inválido: se esperaba JSON")
                continue

            action = message.get("action")

            if action == "set_ready":
                ready = bool(message.get("ready"))
                game_manager.set_player_ready(game_id, username, ready)
                await broadcast_room_sync(game_id)
                if game_manager.are_all_players_ready(game_id):
                    game_manager.set_game_playing(game_id)
                    await database.execute("UPDATE lobbies SET status = 'playing' WHERE id = :id", {"id": int(game_id)})
                    new_state = game_manager.get_game_state(game_id)
                    await manager.broadcast_game_state(game_id, new_state)
                continue

            if action == "chat":
                chat_msg = {
                    "type": "chat_message",
                    "payload": {"sender": username, "message": message.get("message")},
                }
                await manager.broadcast(game_id, chat_msg)
                continue

            if action == "surrender":
                success, msg = await game_manager.surrender_game(game_id, message.get("player"))
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    await manager.broadcast_game_state(game_id, new_state)
                else:
                    await manager.send_error(websocket, msg)
                continue

            if action == "make_move":
                success, msg = await game_manager.make_move(
                    game_id,
                    message.get("player"),
                    message.get("row"),
                    message.get("col"),
                )
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    await manager.broadcast_game_state(game_id, new_state)

                    if new_state["game_over"]:
                        await game_manager.save_game_results(game_id)

                    if new_state["mode"] == "vs_ai" and new_state["current_player"] == "white" and not new_state["game_over"]:
                        await asyncio.sleep(0.5)
                        ai_move = get_best_ai_move(new_state["board"], "white")
                        if ai_move:
                            ai_success, _ = await game_manager.make_move(game_id, "white", ai_move.row, ai_move.col)
                            if ai_success:
                                ai_state = game_manager.get_game_state(game_id)
                                await manager.broadcast_game_state(game_id, ai_state)
                                if ai_state["game_over"]:
                                    await game_manager.save_game_results(game_id)
                else:
                    await manager.send_error(websocket, msg)

    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket, game_id)
        game_state = game_manager.get_game_state(game_id)
        if game_state and game_state["status"] == "waiting":
            game_manager.set_player_ready(game_id, username, False)
            await broadcast_room_sync(game_id)
            return

        if game_state and game_state["status"] == "playing" and not game_state["game_over"]:
            async def abandonment_task():
                try:
                    await asyncio.sleep(30)
                    success, _ = await game_manager.abandon_game(game_id, username)
                    if success:
                        new_state = game_manager.get_game_state(game_id)
                        await manager.broadcast_game_state(game_id, new_state)
                except asyncio.CancelledError:
                    pass

            manager.disconnect_timers[timer_key] = asyncio.create_task(abandonment_task())


@router.websocket("/notifications")
async def notifications_endpoint(websocket: WebSocket, token: str = Query(...)):
    user = await verify_token_ws(token)
    if not user:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token inválido")
        return

    username = user["username"]
    await notifier.connect(websocket, username)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notifier.disconnect(username)
