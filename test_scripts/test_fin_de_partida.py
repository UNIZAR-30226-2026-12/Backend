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
    token = res.json()["access_token"]
    
    me_res = requests.get(f"{BASE_URL}/api/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_res.json()["id"]
    
    return token, user_id

async def test_endgame_flow():
    print("--- Iniciando prueba de Rendicion, ELO e Historial ---")
    u1 = f"perdedor_{uuid.uuid4().hex[:4]}"
    u2 = f"ganador_{uuid.uuid4().hex[:4]}"
    
    print(f"\n1. Creando usuarios: {u1} y {u2} (ELO Inicial: 1000)")
    token1, id1 = create_and_login(u1)
    token2, id2 = create_and_login(u2)
    
    print("2. Creando sala y conectando WebSockets...")
    res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {token1}"}, json={"mode": "1v1"})
    game_id = res.json()["game_id"]
    requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {token2}"})

    async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={token1}") as ws1, \
               websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={token2}") as ws2:
        
        print(f"\n3. {u1} se rinde...")
        await ws1.send(json.dumps({"action": "surrender", "player": "black"}))
        
        # CORRECCIÓN: Leemos el buzón hasta encontrar el estado de fin de partida
        while True:
            estado_str = await asyncio.wait_for(ws1.recv(), timeout=3.0)
            estado = json.loads(estado_str)
            
            if estado.get("type") == "game_state_update" and estado["payload"].get("game_over"):
                print("¡El servidor ha confirmado el final de la partida!")
                print(f"Ganador oficial: {estado['payload']['winner']}")
                break

    # Damos un segundo de margen para que la BBDD termine de escribir
    await asyncio.sleep(1)

    print("\n4. Comprobando la Base de Datos...")
    
    # 4.1 Comprobar ELO
    stats1 = requests.get(f"{BASE_URL}/api/users/{id1}/stats").json()
    stats2 = requests.get(f"{BASE_URL}/api/users/{id2}/stats").json()
    
    print(f"ELO de {u1} tras rendirse: {stats1.get('elo', 'No encontrado')}")
    print(f"ELO de {u2} tras ganar: {stats2.get('elo', 'No encontrado')}")
    
    # 4.2 Comprobar Historial de Partidas
    historial_res = requests.get(f"{BASE_URL}/api/users/me/history", headers={"Authorization": f"Bearer {token1}"})
    
    if historial_res.status_code == 200:
        # CORRECCIÓN: La API devuelve una lista directamente, no un diccionario
        historial = historial_res.json() 
        
        if isinstance(historial, list) and len(historial) > 0:
            partida = historial[0]
            print(f"\nRegistro en Historial de {u1}:")
            print(f"- Rival: {partida.get('opponent_name')}")
            print(f"- Resultado: {partida.get('result')}")
            print(f"- Variacion de ELO: {partida.get('rank_change')}")
            print("\nEXITO TOTAL: El ciclo de partida esta persistiendo en Base de Datos perfectamente.")
        else:
            print("\nFallo: El historial de partidas esta vacio.")
    else:
        print(f"\nFallo al obtener historial. Status: {historial_res.status_code} - {historial_res.text}")

if __name__ == "__main__":
    asyncio.run(test_endgame_flow())