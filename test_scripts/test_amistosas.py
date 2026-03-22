import asyncio
import websockets
import requests
import json
import uuid

BASE_URL = "http://localhost:8081"
WS_URL = "ws://localhost:8081"

def create_and_login(username, password):
    email = f"{username}@test.com"
    requests.post(f"{BASE_URL}/api/auth/register", json={"username": username, "email": email, "password": password})
    res = requests.post(f"{BASE_URL}/api/auth/login", data={"username": username, "password": password})
    return res.json()["access_token"]

async def safe_recv(ws, name, timeout=4.0):
    try:
        msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
        print(f"-> {name} recibe: {msg[:100]}...") 
        return json.loads(msg)
    except asyncio.TimeoutError:
        print(f"TIMEOUT: {name} no recibio nada.")
        return None

async def test_friendly_match_flow():
    print("--- 1. Preparando Usuarios ---")
    u1 = f"retador_{uuid.uuid4().hex[:4]}"
    u2 = f"amigo_{uuid.uuid4().hex[:4]}"
    
    t1 = create_and_login(u1, "pass123")
    t2 = create_and_login(u2, "pass123")
    print(f"Usuarios creados: {u1} y {u2}")

    ws_notif_1 = f"{WS_URL}/ws/notifications?token={t1}"
    ws_notif_2 = f"{WS_URL}/ws/notifications?token={t2}"

    print("\n--- 2. Ambos usuarios abren la app ---")
    async with websockets.connect(ws_notif_1) as notif_ws1, \
               websockets.connect(ws_notif_2) as notif_ws2:
        
        print(f"\n--- 3. {u1} invita a {u2} a jugar ---")
        res_invite = requests.post(
            f"{BASE_URL}/api/games/invite?target_username={u2}", 
            headers={"Authorization": f"Bearer {t1}"}
        )
        game_id = res_invite.json().get("game_id")
        print(f"Respuesta REST de invitacion: {res_invite.json()}")

        #Verificamos si recibe el WebSocket
        aviso_amigo = await safe_recv(notif_ws2, f"{u2} (Notificacion)")
        
        if aviso_amigo and aviso_amigo.get("type") == "duel_invite":
            print(f"\n--- 4. {u2} ACEPTA el duelo ---")
            res_accept = requests.post(
                f"{BASE_URL}/api/games/{game_id}/accept", 
                headers={"Authorization": f"Bearer {t2}"}
            )
            print(f"Respuesta de aceptar: {res_accept.json()}")

            #Verificamos si recibe la confirmación
            confirma_retador = await safe_recv(notif_ws1, f"{u1} (Confirmacion)")

            if confirma_retador and confirma_retador.get("type") == "invite_response":
                print("\n--- 5. Ambos entran a la sala de juego ---")
                ws_play_1 = f"{WS_URL}/ws/play/{game_id}?token={t1}"
                ws_play_2 = f"{WS_URL}/ws/play/{game_id}?token={t2}"

                async with websockets.connect(ws_play_1) as play_ws1:
                    await safe_recv(play_ws1, f"{u1} (Color)")
                    await safe_recv(play_ws1, f"{u1} (Espera)")
                    
                    async with websockets.connect(ws_play_2) as play_ws2:
                        await safe_recv(play_ws2, f"{u2} (Color)")
                        
                        estado1 = await safe_recv(play_ws1, f"{u1} (Tablero)")
                        estado2 = await safe_recv(play_ws2, f"{u2} (Tablero)")

                        if estado1 and estado2:
                            print("\nEXITO TOTAL")
            else:
                print("FALLO: El retador no recibio la confirmacion.")
        else:
            print("FALLO: El amigo no recibio la invitacion por WS.")

if __name__ == "__main__":
    asyncio.run(test_friendly_match_flow())