import asyncio
import websockets
import requests
import json
import uuid

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

def create_and_login(username, password):
    email = f"{username}@test.com"
    requests.post(f"{BASE_URL}/api/auth/register", json={"username": username, "email": email, "password": password})
    res = requests.post(f"{BASE_URL}/api/auth/login", data={"username": username, "password": password})
    return res.json()["access_token"]

async def safe_recv(ws, name):
    try:
        # Esperamos hasta 5 segundos (la IA tarda 0.5s intencionadamente)
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        print(f"-> {name} recibe: {msg[:100]}...") 
        return json.loads(msg)
    except asyncio.TimeoutError:
        print(f"ERROR: {name} se quedó esperando el mensaje (Timeout).")
        return None

async def test_ia_flow():
    print("--- Iniciando prueba de Partida vs IA ---")
    u1 = f"humano_{uuid.uuid4().hex[:4]}"
    
    print(f"\n1. Registrando y logueando usuario '{u1}'...")
    token = create_and_login(u1, "pass123")
    
    print("\n2. Creando sala contra la IA (mode: vs_ai)...")
    res = requests.post(
        f"{BASE_URL}/api/games/create", 
        headers={"Authorization": f"Bearer {token}"},
        json={"mode": "vs_ai"} # <--- Pasamos el nuevo parámetro
    )
    
    if res.status_code != 200:
        print(f"Error creando sala: {res.text}")
        return
        
    game_id = res.json()["game_id"]
    print(f"Sala creada con éxito. ID: {game_id}")
    
    print("\n3. Conectando al WebSocket de la partida...")
    ws_url = f"{WS_URL}/ws/play/{game_id}?token={token}"
    
    async with websockets.connect(ws_url) as ws:
        # 1. El servidor nos asigna color
        await safe_recv(ws, "Asignación de Color")
        
        # 2. Como es vs_ai, el juego empieza YA y manda el tablero inicial
        tablero_inicial = await safe_recv(ws, "Tablero Inicial")
        if not tablero_inicial: return

        print("\n4. Enviando nuestro movimiento: Negras a la fila 2, columna 3...")
        movimiento = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
        await ws.send(json.dumps(movimiento))
        
        # 3. Recibir el tablero después de nuestro movimiento
        print("\nEsperando confirmación de nuestro movimiento...")
        estado_humano = await safe_recv(ws, "Tablero (Post-Humano)")
        
        # 4. LA MAGIA: Recibir el tablero después del contrataque de la IA
        print("\nEsperando el contrataque de la IA...")
        estado_ia = await safe_recv(ws, "Tablero (Post-IA)")
        
        if estado_humano and estado_ia:
            current = estado_ia["payload"]["current_player"]
            ia_move = estado_ia["payload"]["last_move"]
            
            print(f"\n¡ÉXITO TOTAL!")
            print(f"La IA (Minimax) ha respondido moviendo en la posición: {ia_move}")
            print(f"El turno ha vuelto automáticamente a: '{current}'")
        else:
            print("\n Fallo: La IA no respondió a tiempo o hubo un error.")

if __name__ == "__main__":
    asyncio.run(test_ia_flow())