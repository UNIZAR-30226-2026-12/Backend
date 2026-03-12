from fastapi import WebSocket
from typing import Dict

class NotificationManager:
    def __init__(self):
        # Mapea el nombre de usuario a su conexión WebSocket
        self.active_users: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_users[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_users:
            del self.active_users[username]

    async def send_invite(self, target_username: str, creator: str, game_id: str):
        """Busca al amigo y le manda un aviso por WebSocket"""
        if target_username in self.active_users:
            await self.active_users[target_username].send_json({
                "type": "duel_invite",
                "payload": {
                    "creator": creator,
                    "game_id": game_id,
                    "message": f"¡{creator} te ha retado a un duelo!"
                }
            })
            return True # Se envió correctamente
        return False # El amigo está offline

notifier = NotificationManager()