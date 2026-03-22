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

async def safe_recv(ws, name):
    try:
        # Espera un maximo de 3 segundos para no congelarse
        msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
        # Imprime solo los primeros 80 caracteres para no ensuciar la consola
        print(f"-> {name} recibe: {msg[:80]}...") 
        return json.loads(msg)
    except asyncio.TimeoutError:
        print(f"ERROR: {name} se quedo esperando indefinidamente (Timeout).")
        return None

async def test_websocket_flow():
    print("--- Iniciando flujo de prueba ---")
    u1 = f"p1_{uuid.uuid4().hex[:4]}"
    u2 = f"p2_{uuid.uuid4().hex[:4]}"
    
    t1 = create_and_login(u1, "pass123")
    t2 = create_and_login(u2, "pass123")
    
    res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {t1}"})
    game_id = res.json()["game_id"]
    print(f"Sala creada en BD: {game_id}")
    
    async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
        await safe_recv(ws1, "Jugador 1 (Color)")
        await safe_recv(ws1, "Jugador 1 (Aviso Espera)")

        print("\nJugador 2 se une a la sala")
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t2}"})

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
            await safe_recv(ws2, "Jugador 2 (Color)")
            
            print("\nEsperando que el servidor envie el tablero a ambos")
            estado1 = await safe_recv(ws1, "Jugador 1 (Tablero)")
            estado2 = await safe_recv(ws2, "Jugador 2 (Tablero)")

            if estado1 and estado2:
                print("\nExito: Tablero sincronizado en ambos clientes.")
                
                print("Enviando movimiento: Negras a la posicion 2,3...")
                movimiento = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
                await ws1.send(json.dumps(movimiento))
                
                res1 = await safe_recv(ws1, "Jugador 1 (Resultado mov)")
                res2 = await safe_recv(ws2, "Jugador 2 (Resultado mov)")
                
                if res1 and res2:
                    print("\nEXITO TOTAL")
            else:
                print("\nFallo en la sincronizacion del tablero inicial.")

if __name__ == "__main__":
    asyncio.run(test_websocket_flow())