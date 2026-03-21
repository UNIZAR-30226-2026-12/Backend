import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from game.manager import game_manager
from ws.manager import manager

router = APIRouter()

@router.websocket("/play/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    game = game_manager.get_game_state(game_id)
    if not game:
        await websocket.accept()
        await websocket.send_json({"error": "Sala no encontrada"})
        await websocket.close()
        return

    await manager.connect(websocket, game_id)
    # Obtenemos la lista de conexiones actuales de ESTA sala
    conexiones = manager.active_connections.get(game_id, [])
    num_conexiones = len(conexiones)

    # 1. Asignar color
    mi_color = "black" if num_conexiones == 1 else "white"
    await websocket.send_json({"type": "player_assignment", "payload": {"color": mi_color}})

    # 2. Lógica de inicio
    if num_conexiones == 1:
        await websocket.send_json({"type": "waiting_for_player", "payload": {"message": "Esperando a un rival..."}})
    
    elif num_conexiones == 2:
        game_manager.set_game_playing(game_id)
        current_state = game_manager.get_game_state(game_id)
        
        # EN LUGAR DE BROADCAST, ENVIAMOS MANUALMENTE A CADA UNO
        # Esto asegura que nadie se quede fuera
        for conn in conexiones:
            try:
                print(f"DEBUG: Enviando game_state a {conn.client}")
                await conn.send_json({"type": "game_state_update", "payload": current_state})
                print(f"DEBUG: Éxito enviando a {conn.client}")
            except Exception as e:
                print(f"DEBUG: Exception sending state update: {e}")

    # 3. Bucle de juego
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "make_move":
                success, msg = await game_manager.make_move(
                    game_id, message.get("player"), message.get("row"), message.get("col")
                )
                
                if success:
                    new_state = game_manager.get_game_state(game_id)
                    # Aquí sí usamos broadcast porque la partida ya está estable
                    await manager.broadcast_game_state(game_id, new_state)
                else:
                    await manager.send_error(websocket, msg)

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)