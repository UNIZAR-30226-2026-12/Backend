from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        
        # Solo añadimos si no está ya (evita duplicados)
        if websocket not in self.active_connections[game_id]:
            self.active_connections[game_id].append(websocket)
            print(f"DEBUG: Conexión añadida a sala {game_id}. Total: {len(self.active_connections[game_id])}")

    def disconnect(self, websocket: WebSocket, game_id: str):
        if game_id in self.active_connections:
            if websocket in self.active_connections[game_id]:
                self.active_connections[game_id].remove(websocket)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def broadcast_game_state(self, game_id: str, state: dict):
        if game_id in self.active_connections:
            # Hacemos una copia de la lista para evitar errores de iteración
            for connection in list(self.active_connections[game_id]):
                try:
                    await connection.send_json({
                        "type": "game_state_update",
                        "payload": state
                    })
                except Exception as e:
                    print(f"DEBUG: Error enviando a un socket: {e}")

    async def send_error(self, websocket: WebSocket, message: str):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": message}
        })

manager = ConnectionManager()