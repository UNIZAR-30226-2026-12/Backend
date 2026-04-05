import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ai.engine import get_best_ai_move, get_best_ai_move_4p
from auth.dependencies import verify_token_ws
from game.manager import TURN_ORDER_4P, game_manager
from persistence.database import database
from ws.manager import manager
from ws.notifications import notifier

router = APIRouter()

def mode_to_api(mode: str) -> str:
    if mode == "1v1": return "1vs1"
    if mode in ("1v1v1v1", "1vs1vs1vs1"): return "1vs1vs1vs1"
    return mode

async def get_room_players(game: dict) -> List[dict]:
    parts = [u for u in game.get("participants", []) if u and u != "IA"]
    if not parts: return []
    rows = await database.fetch_all("SELECT id, username, elo, avatar_url FROM users WHERE username = ANY(:uns)", {"uns": parts})
    by_un = {r["username"]: r for r in rows}
    
    return [{
        "id": by_un[u]["id"], "username": by_un[u]["username"], "rr": by_un[u]["elo"], 
        "avatar_url": by_un[u]["avatar_url"], "is_ready": bool(game.get("players_ready", {}).get(u, False))
    } for u in parts if u in by_un]

async def broadcast_room_sync(game_id: str):
    game = game_manager.get_game_state(game_id)
    if game:
        await manager.broadcast(game_id, {
            "type": "room_sync", 
            "payload": {"game_id": game_id, "status": game.get("status", "waiting"), "mode": mode_to_api(game.get("mode", "1v1")), "players": await get_room_players(game)}
        })

def ensure_user_assigned_to_game(game: dict, username: str) -> Optional[str]:
    if game.get("mode") == "1v1v1v1":
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

@router.websocket("/play/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, token: str = Query(...)):
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

    await manager.connect(websocket, game_id)
    timer_key = f"{game_id}_{username}"
    if timer_key in manager.disconnect_timers:
        manager.disconnect_timers[timer_key].cancel()
        del manager.disconnect_timers[timer_key]

    was_paused = username in game.get("paused_usernames", [])
    if was_paused:
        game_manager.resume_player(game_id, username)
        await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))

    await websocket.send_json({"type": "player_assignment", "payload": {"color": assigned_piece}})
    game.setdefault("players_ready", {})[username] = False

    if game.get("mode") == "vs_ai":
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

    try:
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
                await manager.broadcast_game_state(game_id, game)
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
                await manager.broadcast(game_id, {"type": "chat_message", "payload": {"sender": username, "message": message.get("message")}})
                continue

            if action == "pause":
                success, msg = game_manager.pause_player(game_id, username)
                if success:
                    await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))
                else:
                    await manager.send_error(websocket, msg)
                continue

            if action == "surrender":
                if game.get("mode") == "vs_ai":
                    success, msg = await game_manager.surrender_game(game_id, assigned_piece)
                else:
                    # En partidas online (publicas o con amigos) tratamos "abandonar"
                    # como abandono real del usuario para respetar las reglas de pausa/invalidez.
                    success, msg = await game_manager.abandon_game(game_id, username)
                if success:
                    ns = game_manager.get_game_state(game_id)
                    if ns and ns.get("game_over"): await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                    await manager.broadcast_game_state(game_id, ns)
                else: await manager.send_error(websocket, msg)
                continue

            if action == "make_move":
                success, msg = await game_manager.make_move(game_id, assigned_piece, message.get("row"), message.get("col"))
                if success:
                    ns = game_manager.get_game_state(game_id)
                    if ns and ns.get("game_over"): await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                    await manager.broadcast_game_state(game_id, ns)

                    def check_and_trigger_ai(current_state):
                        if not current_state or current_state.get("game_over"): return
                        
                        c_player = current_state.get("current_player")
                        g_mode = game.get("mode", "1v1")
                        
                        is_1v1_ai = (g_mode == "vs_ai" and c_player == "white")
                        u_name = current_state.get("username_by_piece", {}).get(c_player)
                        is_4p_ai = (g_mode in ("1v1v1v1", "1vs1vs1vs1") and u_name and u_name.startswith("IA_"))

                        if is_1v1_ai or is_4p_ai:
                            async def play_ai_turn():
                                await asyncio.sleep(0.5)
                                if is_4p_ai:
                                    ai_move = await asyncio.to_thread(get_best_ai_move_4p, current_state["board"], c_player)
                                    r, c = (ai_move["row"], ai_move["col"]) if ai_move else (None, None)
                                else:
                                    ai_move = await asyncio.to_thread(get_best_ai_move, current_state["board"], c_player)
                                    r, c = (ai_move.row, ai_move.col) if ai_move else (None, None)
                                
                                if r is not None and c is not None:
                                    ai_success, _ = await game_manager.make_move(game_id, c_player, r, c)
                                    if ai_success:
                                        ais = game_manager.get_game_state(game_id)
                                        if ais and ais.get("game_over"): 
                                            await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                                        await manager.broadcast_game_state(game_id, ais)
                                        
                                        check_and_trigger_ai(ais)

                            asyncio.create_task(play_ai_turn())

                    check_and_trigger_ai(ns)
                    
                else: await manager.send_error(websocket, msg)
                continue

    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket, game_id)
        if not (game := game_manager.get_game_state(game_id)): return

        if game.get("status") == "waiting":
            # Si el host de una partida pública se desconecta, cerramos la sala para evitar "fantasmas" en la lista
            lobby = await database.fetch_one("SELECT creator_id, is_public, id FROM lobbies WHERE id = :id", {"id": int(game_id)})
            
            # Asegurar comparacion de enteros para evitar errores de tipo
            is_host = lobby and int(lobby["creator_id"]) == int(user["id"])
            is_public = lobby and lobby["is_public"]
            print(f"WS DEBUG: {username} (Host={is_host}, Public={is_public}) disconnected from room {game_id}")
            
            if is_host and is_public:
                # Destruir lobby público porque el host se ha ido
                await database.execute("DELETE FROM lobbies WHERE id = :id", {"id": int(game_id)})
                game_manager.remove_game(game_id)
                
                # Desconectar a todos los demás de este socket de sala enviando mensaje de error
                await manager.broadcast(game_id, {"type": "error", "payload": {"message": "El host ha abandonado la sala. Partida cancelada."}})
                
                # Notificar por el canal de notificaciones global que la sala se ha cerrado
                parts = game.get("participants", [])
                for p in parts:
                    if p != username:
                        print(f"WS DEBUG: Sending room_closed to {p}")
                        await notifier.send_invite_response(target_username=p, game_id=game_id, action="room_closed", guest=username)
            else:
                # Si se va un invitado o un host de partida privada, lo quitamos del estado de juego
                if username in game.get("participants", []):
                    game["participants"].remove(username)
                    game.get("players_ready", {}).pop(username, None)
                    
                    # Si es una partida privada/invitación, marcar en DB como que se ha ido
                    await database.execute("DELETE FROM lobby_invites WHERE lobby_id = :id AND invited_user_id = :uid", 
                                        {"id": int(game_id), "uid": user["id"]})
                
                # Sincronizar el estado (ahora falta un jugador)
                await broadcast_room_sync(game_id)

                # Notificar a otros que alguien se ha ido (pero la sala SIGUE abierta)
                # Usar action="left" en lugar de "room_closed"
                parts = game.get("participants", [])
                for p in parts:
                    if p != username:
                        print(f"WS DEBUG: Sending left action to {p}")
                        await notifier.send_invite_response(target_username=p, game_id=game_id, action="left", guest=username)
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
                        if ns and ns.get("game_over"): await database.execute("UPDATE lobbies SET status = 'finished' WHERE id = :id", {"id": int(game_id)})
                        await manager.broadcast_game_state(game_id, ns)
                except asyncio.CancelledError: pass
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
