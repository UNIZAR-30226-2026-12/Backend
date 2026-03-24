import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from game.manager import game_manager
from ws.manager import manager
from ws.notifications import notifier
from auth.dependencies import verify_token_ws
from ai.engine import get_best_ai_move

router = APIRouter()

@router.websocket("/play/{game_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    game_id: str, 
    token: str = Query(...) 
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
    
    # --- SISTEMA DE RECONEXIÓN ---
    # Cancelar el temporizador de desconexión si el usuario volvió a tiempo
    timer_key = f"{game_id}_{username}"
    if timer_key in manager.disconnect_timers:
        manager.disconnect_timers[timer_key].cancel()
        del manager.disconnect_timers[timer_key]
        print(f"DEBUG: {username} se ha reconectado. Abandono cancelado.")

    # Asignación inteligente de color por si es una reconexión
    if game.get("black_player") == username:
        mi_color = "black"
    elif game.get("white_player") == username:
        mi_color = "white"
    else:
        # Nuevo jugador
        mi_color = "black" if not game.get("black_player") else "white"

    await websocket.send_json({"type": "player_assignment", "payload": {"color": mi_color}})

    if mi_color == "white" and not game.get("white_player"):
        game["white_player"] = username
    elif mi_color == "black" and not game.get("black_player"):
        game["black_player"] = username

    # Lógica de inicio dependiendo del MODO
    conexiones = manager.active_connections.get(game_id, [])
    num_conexiones = len(conexiones)
    
    if game["mode"] == "vs_ai":
        game_manager.set_game_playing(game_id)
        current_state = game_manager.get_game_state(game_id)    
        await manager.broadcast_game_state(game_id, current_state)
    elif num_conexiones == 1 and game["status"] == "waiting":
        await websocket.send_json({"type": "waiting_for_player", "payload": {"message": "Esperando a un rival..."}})
    elif num_conexiones > 0 and game["status"] == "playing":
        # Si la partida ya empezó (ej. es una reconexión o entra el jugador 2)
        game_manager.set_game_playing(game_id)
        current_state = game_manager.get_game_state(game_id)    
        await manager.broadcast_game_state(game_id, current_state)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "chat":
                chat_msg = {
                    "type": "chat_message",
                    "payload": {
                        "sender": username,
                        "message": message.get("message")
                    }
                }
                for connection in manager.active_connections.get(game_id, []):
                    try:
                        await connection.send_json(chat_msg)
                    except Exception:
                        pass
                        
            elif message.get("action") == "surrender":
                success, msg = await game_manager.surrender_game(game_id, message.get("player"))
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    await manager.broadcast_game_state(game_id, new_state)
                else:
                    await manager.send_error(websocket, msg)
                        
            elif message.get("action") == "make_move":
                success, msg = await game_manager.make_move(
                    game_id, message.get("player"), message.get("row"), message.get("col")
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
                            ai_success, ai_msg = await game_manager.make_move(
                                game_id, "white", ai_move.row, ai_move.col
                            )
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
        if game_state and game_state["status"] == "playing" and not game_state["game_over"]:
            
            async def abandonment_task():
                try:
                    await asyncio.sleep(30)
                    success, _ = await game_manager.abandon_game(game_id, username)
                    if success:
                        new_state = game_manager.get_game_state(game_id)
                        await manager.broadcast_game_state(game_id, new_state)
                        print(f"DEBUG: {username} no volvió a la sala {game_id}. Partida dada por perdida.")
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