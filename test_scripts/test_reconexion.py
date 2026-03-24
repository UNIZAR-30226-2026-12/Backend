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

async def safe_recv(ws):
    try:
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        return json.loads(msg)
    except asyncio.TimeoutError:
        return None

async def test_reconnection_flows():
    print("--- Iniciando pruebas de Desconexion y Reconexion ---")
    
    # ==========================================
    # TEST 1: RECONEXION EXITOSA (Microcorte)
    # ==========================================
    print("\n--- TEST 1: Reconexion Exitosa (Microcorte 0.2 segundos) ---")
    u1 = f"recon_{uuid.uuid4().hex[:4]}"
    u2 = f"rival_{uuid.uuid4().hex[:4]}"
    t1 = create_and_login(u1)
    t2 = create_and_login(u2)
    
    res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {t1}"}, json={"mode": "1v1"})
    game_id = res.json()["game_id"]
    requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t2}"})

    print(f"1. {u2} (Rival) se conecta y espera.")
    async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
        await safe_recv(ws2)
        
        print(f"2. {u1} entra a la partida...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
            await safe_recv(ws1)
            print(f"3. {u1} cierra la pestana (Desconexion abrupta)...")
            
        print("4. Esperando 0.2 segundos (simulando corte ultrarrapido)...")
        await asyncio.sleep(0.2)
        
        print(f"5. {u1} vuelve a abrir el juego y se reconecta...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1_reconnect:
            asignacion = await safe_recv(ws1_reconnect)
            print(f"   Color restaurado por el servidor: {asignacion['payload']['color']}")
            
            tablero = await safe_recv(ws1_reconnect)
            if tablero and not tablero["payload"].get("game_over"):
                print("EXITO T1: La partida sigue viva, el servidor cancelo el abandono a tiempo.")
            else:
                print("FALLO T1: La partida se cerro prematuramente.")

    # ==========================================
    # TEST 2: ABANDONO DEFINITIVO (Timeout)
    # ==========================================
    print("\n--- TEST 2: Abandono por Timeout (Ragequit) ---")
    u3 = f"aban_{uuid.uuid4().hex[:4]}"
    u4 = f"gana_{uuid.uuid4().hex[:4]}"
    t3 = create_and_login(u3)
    t4 = create_and_login(u4)
    
    res2 = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {t3}"}, json={"mode": "1v1"})
    game_id2 = res2.json()["game_id"]
    requests.post(f"{BASE_URL}/api/games/join/{game_id2}", headers={"Authorization": f"Bearer {t4}"})

    async with websockets.connect(f"{WS_URL}/ws/play/{game_id2}?token={t4}") as ws4:
        await safe_recv(ws4)
        
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id2}?token={t3}") as ws3:
            await safe_recv(ws3)
            print(f"1. {u3} se conecta a la partida y se desconecta para no volver.")
        
        print("2. Esperando 4 segundos (el limite del servidor para test)...")
        
        while True:
            estado = await safe_recv(ws4)
            if not estado:
                print("FALLO T2: El servidor no declaro abandono, el rival sigue esperando infinitamente.")
                break
                
            if estado.get("type") == "game_state_update" and estado["payload"].get("game_over"):
                print(f"EXITO T2: El servidor declaro el abandono.")
                print(f"   Ganador oficial: {estado['payload']['winner']}")
                break

if __name__ == "__main__":
    asyncio.run(test_reconnection_flows())