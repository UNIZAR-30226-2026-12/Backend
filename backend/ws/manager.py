from fastapi import WebSocket
from typing import Dict, List
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.disconnect_timers: Dict[str, asyncio.Task] = {}
        self.active_users: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, game_id: str, username: str) -> bool:
        from starlette.websockets import WebSocketState
        prev_ws = self.active_users.get(username)
        if prev_ws is not None:
            # Solo bloquear si la sesion anterior sigue activa (no cerrada por el cliente)
            prev_still_open = prev_ws.client_state == WebSocketState.CONNECTED
            if prev_still_open:
                await websocket.accept()
                await websocket.close(code=1008, reason="Ya tienes una sesion activa en otro lugar")
                print(f"DEBUG: Doble conexion bloqueada para '{username}' en sala {game_id}")
                return False
            else:
                # Sesion anterior ya cerrada: limpiar rastro obsoleto antes de reconectar
                self.disconnect(prev_ws, game_id, username)
                print(f"DEBUG: Sesion obsoleta de '{username}' limpiada automaticamente antes de reconectar")

        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []

        if websocket not in self.active_connections[game_id]:
            self.active_connections[game_id].append(websocket)

        self.active_users[username] = websocket
        print(f"DEBUG: Conexion añadida para '{username}' en sala {game_id}. Total: {len(self.active_connections[game_id])}")
        return True

    def disconnect(self, websocket: WebSocket, game_id: str, username: str = None):
        if game_id in self.active_connections:
            if websocket in self.active_connections[game_id]:
                self.active_connections[game_id].remove(websocket)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

        if username and self.active_users.get(username) is websocket:
            del self.active_users[username]

    async def broadcast(self, game_id: str, message: dict):
        if game_id in self.active_connections:
            for connection in list(self.active_connections[game_id]):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"DEBUG: Error enviando a un socket en sala {game_id}: {e}")
                    self.disconnect(connection, game_id)

    async def broadcast_game_state(self, game_id: str, state: dict):
        await self.broadcast(game_id, {
            "type": "game_state_update",
            "payload": state
        })

    async def send_error(self, websocket: WebSocket, message: str):
        await websocket.send_json({
            "type": "error",
            "payload": {"message": message}
        })

manager = ConnectionManager()