import asyncio
import json
from typing import List, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ai.engine import get_best_ai_move
from auth.dependencies import verify_token_ws
from game.manager import PIECES_4P, TURN_ORDER_4P, game_manager
from persistence.database import database
from ws.manager import manager
from ws.notifications import notifier

router = APIRouter()


def mode_to_api(mode: str) -> str:
    if mode == "1v1":
        return "1vs1"
    if mode in ("1v1v1v1", "1vs1vs1vs1"):
        return "1vs1vs1vs1"
    return mode


async def get_room_players(game: dict) -> List[dict]:
    participants = [username for username in game.get("participants", []) if username and username != "IA"]
    if not participants:
        return []

    rows = await database.fetch_all(
        """
        SELECT id, username, elo, avatar_url
        FROM users
        WHERE username = ANY(:usernames)
        """,
        {"usernames": participants},
    )
    by_username = {row["username"]: row for row in rows}

    players = []
    ready_map = game.get("players_ready", {})
    for username in participants:
        row = by_username.get(username)
        if not row:
            continue
        players.append(
            {
                "id": row["id"],
                "username": row["username"],
                "rr": row["elo"],
                "avatar_url": row["avatar_url"],
                "is_ready": bool(ready_map.get(username, False)),
            }
        )
    return players


async def broadcast_room_sync(game_id: str):
    game = game_manager.get_game_state(game_id)
    if not game:
        return

    players = await get_room_players(game)
    await manager.broadcast(
        game_id,
        {
            "type": "room_sync",
            "payload": {
                "game_id": game_id,
                "status": game.get("status", "waiting"),
                "mode": mode_to_api(game.get("mode", "1v1")),
                "players": players,
            },
        },
    )


def ensure_user_assigned_to_game(game: dict, username: str) -> Optional[str]:
    mode = game.get("mode")
    if mode == "1v1v1v1":
        piece = game.get("piece_by_username", {}).get(username)
        if piece:
            return piece

        if username in game.get("participants", []):
            # Participante esperado pero aun no asignado.
            for next_piece in TURN_ORDER_4P:
                if not game.get("username_by_piece", {}).get(next_piece):
                    game["username_by_piece"][next_piece] = username
                    game["piece_by_username"][username] = next_piece
                    if next_piece not in game.get("active_pieces", []):
                        game["active_pieces"].append(next_piece)
                    game.setdefault("players_ready", {})[username] = False
                    return next_piece
            return None

        expected_count = game.get("participant_count_expected", 4)
        if len(game.get("participants", [])) >= expected_count:
            return None

        # Fallback para salas abiertas incompletas.
        game.setdefault("participants", []).append(username)
        game.setdefault("players_ready", {})[username] = False
        for next_piece in TURN_ORDER_4P:
            if not game.get("username_by_piece", {}).get(next_piece):
                game["username_by_piece"][next_piece] = username
                game["piece_by_username"][username] = next_piece
                if next_piece not in game.get("active_pieces", []):
                    game["active_pieces"].append(next_piece)
                return next_piece
        return None

    if game.get("black_player") == username:
        return "black"
    if game.get("white_player") == username:
        return "white"

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


@router.websocket("/play/{game_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    token: str = Query(...),
):
    user = await verify_token_ws(token)
    if not user:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token invalido")
        return

    username = user["username"]
    game = game_manager.get_game_state(game_id)
    if not game:
        await websocket.accept()
        await websocket.send_json({"error": "Sala no encontrada"})
        await websocket.close()
        return

    assigned_piece = ensure_user_assigned_to_game(game, username)
    if not assigned_piece:
        await websocket.accept()
        await websocket.send_json({"type": "error", "payload": {"message": "La sala esta llena"}})
        await websocket.close()
        return

    await manager.connect(websocket, game_id)

    timer_key = f"{game_id}_{username}"
    if timer_key in manager.disconnect_timers:
        manager.disconnect_timers[timer_key].cancel()
        del manager.disconnect_timers[timer_key]

    await websocket.send_json({"type": "player_assignment", "payload": {"color": assigned_piece}})

    game.setdefault("players_ready", {})
    game["players_ready"].setdefault(username, False)

    if game.get("mode") == "vs_ai":
        game_manager.set_game_playing(game_id)
        await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))
    else:
        await broadcast_room_sync(game_id)
        if game.get("status") == "waiting":
            await websocket.send_json(
                {
                    "type": "waiting_for_player",
                    "payload": {"message": "Esperando a que todos esten listos..."},
                }
            )
        else:
            await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                await manager.send_error(websocket, "Formato de mensaje invalido: se esperaba JSON")
                continue

            action = message.get("action")

            if action == "set_ready":
                ready = bool(message.get("ready"))
                game_manager.set_player_ready(game_id, username, ready)
                await broadcast_room_sync(game_id)
                if game_manager.are_all_players_ready(game_id):
                    game_manager.set_game_playing(game_id)
                    await database.execute("UPDATE lobbies SET status = 'playing' WHERE id = :id", {"id": int(game_id)})
                    await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))
                continue

            if action == "chat":
                await manager.broadcast(
                    game_id,
                    {
                        "type": "chat_message",
                        "payload": {"sender": username, "message": message.get("message")},
                    },
                )
                continue

            if action == "surrender":
                mode = game.get("mode")
                if mode == "1v1v1v1":
                    success, msg = await game_manager.surrender_game(game_id, username)
                else:
                    success, msg = await game_manager.surrender_game(game_id, assigned_piece)
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    if new_state and new_state.get("game_over"):
                        await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                    await manager.broadcast_game_state(game_id, new_state)
                else:
                    await manager.send_error(websocket, msg)
                continue

            if action == "make_move":
                mode = game.get("mode")
                player_piece = assigned_piece
                row = message.get("row")
                col = message.get("col")
                success, msg = await game_manager.make_move(game_id, player_piece, row, col)
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    if new_state and new_state.get("game_over"):
                        await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                    await manager.broadcast_game_state(game_id, new_state)

                    if (
                        mode == "vs_ai"
                        and new_state
                        and new_state.get("current_player") == "white"
                        and not new_state.get("game_over")
                    ):
                        await asyncio.sleep(0.5)
                        ai_move = get_best_ai_move(new_state["board"], "white")
                        if ai_move:
                            ai_success, _ = await game_manager.make_move(game_id, "white", ai_move.row, ai_move.col)
                            if ai_success:
                                ai_state = game_manager.get_game_state(game_id)
                                if ai_state and ai_state.get("game_over"):
                                    await database.execute(
                                        "UPDATE lobbies SET status = 'finished' WHERE id = :id",
                                        {"id": int(game_id)},
                                    )
                                await manager.broadcast_game_state(game_id, ai_state)
                else:
                    await manager.send_error(websocket, msg)
                continue

    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket, game_id)
        game_state = game_manager.get_game_state(game_id)
        if not game_state:
            return

        if game_state.get("status") == "waiting":
            game_manager.set_player_ready(game_id, username, False)
            await broadcast_room_sync(game_id)
            return

        if game_state.get("status") == "playing" and not game_state.get("game_over"):
            async def abandonment_task():
                try:
                    await asyncio.sleep(30)
                    success, _ = await game_manager.abandon_game(game_id, username)
                    if success:
                        new_state = game_manager.get_game_state(game_id)
                        if new_state and new_state.get("game_over"):
                            await database.execute(
                                "UPDATE lobbies SET status = 'finished' WHERE id = :id",
                                {"id": int(game_id)},
                            )
                        await manager.broadcast_game_state(game_id, new_state)
                except asyncio.CancelledError:
                    pass

            manager.disconnect_timers[timer_key] = asyncio.create_task(abandonment_task())


@router.websocket("/notifications")
async def notifications_endpoint(websocket: WebSocket, token: str = Query(...)):
    user = await verify_token_ws(token)
    if not user:
        await websocket.accept()
        await websocket.close(code=1008, reason="Token invalido")
        return

    username = user["username"]
    await notifier.connect(websocket, username)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notifier.disconnect(username)
