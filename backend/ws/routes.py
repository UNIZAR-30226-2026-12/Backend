from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from game.manager import game_manager
from ws.manager import manager
from ws.notifications import notifier
import json

router = APIRouter()

@router.websocket("/play/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    game = game_manager.get_game_state(game_id)
    if not game:
        await websocket.accept()
        await manager.send_error(websocket, "Sala no encontrada")
        await websocket.close()
        return

    await manager.connect(websocket, game_id)

    # LÓGICA DE SALA: ¿Es el creador esperando, o el Jugador 2 conectándose?
    conexiones_actuales = len(manager.active_connections[game_id])
    mi_color = "black" if conexiones_actuales == 1 else "white"

    await websocket.send_json({
        "type": "player_assignment",
        "payload": {"color": mi_color}
    })

    if game["status"] in ["waiting", "private"]:
        if conexiones_actuales == 1:
            # Es el creador, lo dejamos esperando en la sala
            await websocket.send_json({"type": "waiting_for_player", "payload": {"message": "Esperando a que se una un rival..."}})
        elif conexiones_actuales == 2:
            # ¡Acaba de entrar el Jugador 2! Arrancamos la partida
            game_manager.set_game_playing(game_id)
            await manager.broadcast_game_state(game_id, game_manager.get_game_state(game_id))
    elif game["status"] == "playing":
        # Se ha reconectado alguien en una partida en curso
        await websocket.send_json({"type": "game_state_update", "payload": game})

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "make_move":
                row = message.get("row")
                col = message.get("col")
                player = message.get("player")
                
                success, msg = game_manager.make_move(game_id, player, row, col)
                
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    await manager.broadcast_game_state(game_id, new_state)
                else:
                    await manager.send_error(websocket, msg)

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)
        # Más adelante avisar de "El rival ha abandonado la sala"

@router.websocket("/notifications/{username}")
async def websocket_notifications(websocket: WebSocket, username: str):
    await notifier.connect(websocket, username)
    try:
        while True:
            await websocket.receive_text() # Mantiene la conexión viva
    except WebSocketDisconnect:
        notifier.disconnect(username)