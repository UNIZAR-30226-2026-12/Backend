import asyncio
import websockets
import requests
import json
import uuid

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

def create_and_login(username):
    requests.post(f"{BASE_URL}/api/auth/register", json={"username": username, "email": f"{username}@test.com", "password": "123"})
    res = requests.post(f"{BASE_URL}/api/auth/login", data={"username": username, "password": "123"})
    return res.json()["access_token"]

# AÑADIDO: Un filtro para saber de quién esperamos el mensaje
async def wait_for_chat(ws, name, expected_sender=None):
    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(msg)
            if data.get("type") == "chat_message":
                sender = data['payload']['sender']
                
                if expected_sender and sender != expected_sender:
                    continue
                    
                print(f"-> {name} leyó el mensaje: [{sender}] {data['payload']['message']}")
                return data
    except asyncio.TimeoutError:
        print(f"ERROR: {name} no recibió ningún mensaje de chat a tiempo.")
        return None

async def test_chat_flow():
    print("--- Iniciando prueba de Chat Bidireccional ---")
    u1 = f"userA_{uuid.uuid4().hex[:4]}"
    u2 = f"userB_{uuid.uuid4().hex[:4]}"
    
    print("\n1. Preparando jugadores...")
    token1 = create_and_login(u1)
    token2 = create_and_login(u2)
    
    print("2. Creando sala y conectando...")
    res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {token1}"}, json={"mode": "1v1"})
    game_id = res.json()["game_id"]
    requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {token2}"})

    async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={token1}") as ws1, \
               websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={token2}") as ws2:
        
        print(f"\n3. {u1} envía un saludo por el chat...")
        mensaje_u1 = {"action": "chat", "message": "¡Hola rival, buena suerte!"}
        await ws1.send(json.dumps(mensaje_u1))
        
        # u2 espera un mensaje DE u1
        recibido_u2 = await wait_for_chat(ws2, u2, expected_sender=u1)
        
        if recibido_u2 and recibido_u2["payload"]["message"] == "¡Hola rival, buena suerte!":
            print(f"\n4. {u2} responde...")
            mensaje_u2 = {"action": "chat", "message": "¡Gracias, igualmente!"}
            await ws2.send(json.dumps(mensaje_u2))
            
            # u1 espera un mensaje DE u2 (así ignora el suyo propio)
            recibido_u1 = await wait_for_chat(ws1, u1, expected_sender=u2)
            
            if recibido_u1 and recibido_u1["payload"]["sender"] == u2:
                print("\n¡ÉXITO TOTAL! El chat en tiempo real funciona perfectamente bidireccional.")
            else:
                print("Fallo: El Usuario 1 no recibió la respuesta.")
        else:
            print("Fallo: El mensaje inicial no llegó correctamente.")

if __name__ == "__main__":
    asyncio.run(test_chat_flow())