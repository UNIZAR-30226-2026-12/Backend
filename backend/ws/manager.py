from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        if game_id in self.active_connections:
            if websocket in self.active_connections[game_id]:
                self.active_connections[game_id].remove(websocket)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def broadcast_game_state(self, game_id: str, state: dict):
        """Envía el tablero actualizado a todos los jugadores de esa sala"""
        if game_id in self.active_connections:
            for connection in self.active_connections[game_id]:
                await connection.send_json({
                    "type": "game_state_update",
                    "payload": state
                })
                
    async def send_error(self, websocket: WebSocket, message: str):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": message}
        })

manager = ConnectionManager()