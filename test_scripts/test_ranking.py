import requests
import uuid

BASE_URL = "http://localhost:8000"

def test_ranking_flow():
    print("--- Iniciando prueba del Leaderboard (Ránking) ---")
    
    # 1. Creamos un usuario rápido para asegurarnos de que la DB tiene a alguien
    dummy_name = f"jugador_top_{uuid.uuid4().hex[:4]}"
    print(f"\n1. Registrando usuario de prueba: '{dummy_name}'...")
    requests.post(
        f"{BASE_URL}/api/auth/register", 
        json={"username": dummy_name, "email": f"{dummy_name}@test.com", "password": "pass"}
    )
    
    # 2. Hacemos la petición al nuevo endpoint de ranking
    print("\n2. Solicitando el Top 50 Global al servidor...")
    response = requests.get(f"{BASE_URL}/api/ranking/")
    
    if response.status_code == 200:
        data = response.json()
        ranking = data.get("ranking", [])
        
        print("\n¡ÉXITO! Ránking recibido correctamente:")
        print(f"Total de jugadores en el Top: {len(ranking)}")
        
        # Imprimimos los 3 primeros para no saturar la consola
        print("\n--- TOP 3 ---")
        for i, player in enumerate(ranking[:3]):
            print(f" #{i+1} | {player['username']} | ELO: {player['elo']}")
            
    else:
        print(f"Fallo al obtener el ránking. Código HTTP: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_ranking_flow()