from fastapi import WebSocket
from typing import Dict


class NotificationManager:
    def __init__(self):
        self.active_users: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_users[username] = websocket
        print(f"NOTIFICACIONES: {username} se ha conectado.")

    def disconnect(self, username: str):
        if username in self.active_users:
            del self.active_users[username]
            print(f"NOTIFICACIONES: {username} se ha desconectado.")

    async def send_invite(self, target_username: str, creator: str, game_id: str, mode: str):
        if target_username in self.active_users:
            await self.active_users[target_username].send_json({
                "type": "duel_invite",
                "payload": {
                    "creator": creator,
                    "game_id": game_id,
                    "mode": mode,
                    "message": f"{creator} te ha invitado a jugar una partida {mode}, puedes aceptarla desde la pestaña de amigos.",
                },
            })
            return True
        return False

    async def send_invite_response(self, target_username: str, game_id: str, action: str, guest: str):
        if target_username in self.active_users:
            message = ""
            if action == "accepted":
                message = f"{guest} ha aceptado tu invitación."
            elif action == "rejected":
                message = f"{guest} ha rechazado tu invitación."
            elif action == "left":
                message = f"{guest} ha abandonado la sala."
            elif action == "room_closed":
                message = f"El host {guest} ha abandonado la sala. La partida ha sido cancelada."
            elif action == "kicked":
                message = f"Has sido expulsado de la sala por {guest}."

            await self.active_users[target_username].send_json({
                "type": "invite_response",
                "payload": {
                    "game_id": game_id,
                    "action": action,
                    "guest": guest,
                    "message": message,
                },
            })
            return True
        return False


notifier = NotificationManager()
