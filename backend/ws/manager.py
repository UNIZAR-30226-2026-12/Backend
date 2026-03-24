from fastapi import WebSocket
from typing import Dict, List
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.disconnect_timers: Dict[str, asyncio.Task] = {}  

    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        
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