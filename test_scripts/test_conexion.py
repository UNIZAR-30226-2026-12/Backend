import requests
import uuid

BASE_URL = "http://localhost:8081"

def create_and_login(username, password):
    email = f"{username}@test.com"
    requests.post(f"{BASE_URL}/api/auth/register", json={"username": username, "email": email, "password": password})
    response = requests.post(f"{BASE_URL}/api/auth/login", data={"username": username, "password": password})
    return response.json()["access_token"]

def test_online_multiplayer_flow():
    # 1. Crear dos usuarios
    u1_name = f"host_{uuid.uuid4().hex[:4]}"
    u2_name = f"guest_{uuid.uuid4().hex[:4]}"
    
    print(f"--- 1. Creando usuarios: {u1_name} y {u2_name} ---")
    token_1 = create_and_login(u1_name, "pass123")
    token_2 = create_and_login(u2_name, "pass123")
    
    headers_1 = {"Authorization": f"Bearer {token_1}"}
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    # 2. Usuario 1 crea una sala pública
    print(f"\n--- 2. {u1_name} crea una sala pública ---")
    response = requests.post(f"{BASE_URL}/api/games/create", headers=headers_1)
    if response.status_code == 200:
        data = response.json()
        game_id = data["game_id"]
        print(f"Sala creada con éxito! ID: {game_id}")
    else:
        print(f"Error al crear sala: {response.text}")
        return

    # 3. Usuario 2 busca salas públicas
    print(f"\n--- 3. {u2_name} busca salas públicas ---")
    response = requests.get(f"{BASE_URL}/api/games/public")
    if response.status_code == 200:
        lobbies = response.json()["lobbies"]
        print(f"Salas encontradas: {len(lobbies)}")
        for lobby in lobbies:
            print(f"   - Sala de: {lobby['creator']} (ID: {lobby['game_id']})")
    else:
        print(f"Error al listar salas: {response.text}")
        return

    # 4. Usuario 2 se une a la sala del Usuario 1
    print(f"\n--- 4. {u2_name} se une a la sala {game_id} ---")
    response = requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers=headers_2)
    if response.status_code == 200:
        print(f"Unión exitosa! Mensaje: {response.json()['message']}")
    else:
        print(f"Error al unirse a la sala: {response.text}")
        return
        
    # 5. Intentar unirse a la misma sala (debería dar error porque ya está llena)
    print(f"\n--- 5. Intentando unirse a una sala llena ---")
    response = requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers=headers_1)
    if response.status_code == 400:
        print(f"El sistema bloqueó la entrada. Mensaje: {response.json()['detail']}")
    else:
        print(f"Cuidado, dejó entrar a un tercer jugador o falló distinto: {response.status_code}")

if __name__ == "__main__":
    test_online_multiplayer_flow()