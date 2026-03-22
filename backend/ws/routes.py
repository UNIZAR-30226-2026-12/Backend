import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from game.manager import game_manager
from ws.manager import manager
from ws.notifications import notifier
from auth.dependencies import verify_token_ws

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
        

    game = game_manager.get_game_state(game_id)
    if not game:
        await websocket.accept()
        await websocket.send_json({"error": "Sala no encontrada"})
        await websocket.close()
        return

    await manager.connect(websocket, game_id)
    conexiones = manager.active_connections.get(game_id, [])
    num_conexiones = len(conexiones)

    mi_color = "black" if num_conexiones == 1 else "white"
    await websocket.send_json({"type": "player_assignment", "payload": {"color": mi_color}})

    if num_conexiones == 1:
        await websocket.send_json({"type": "waiting_for_player", "payload": {"message": "Esperando a un rival..."}})
    elif num_conexiones == 2:
        game_manager.set_game_playing(game_id)
        
        current_state = game_manager.get_game_state(game_id)    
        await manager.broadcast_game_state(game_id, current_state)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "make_move":
                # Aquí se podría añadir una seguridad validando 
                # que el jugador que manda el movimiento coincide con su username
                success, msg = await game_manager.make_move(
                    game_id, message.get("player"), message.get("row"), message.get("col")
                )
                
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    await manager.broadcast_game_state(game_id, new_state)
                else:
                    await manager.send_error(websocket, msg)

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)

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