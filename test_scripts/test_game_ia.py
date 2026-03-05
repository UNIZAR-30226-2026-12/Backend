import requests

BASE_URL = "http://localhost:8000"

def test_game_flow():
    # 1. Create a new game
    print("--- 1. Creating a new game ---")
    response = requests.post(f"{BASE_URL}/partida")
    if response.status_code == 200:
        game_state = response.json()
        game_id = game_state["game_id"]
        print(f"Game created! ID: {game_id}")
        print(f"Score: {game_state['score']}")
    else:
        print(f"Failed to create game: {response.status_code} - {response.text}")
        return

    # 2. Make a move
    # In Reversi, valid moves are usually around the center for 'black' (first player)
    # The initial board is:
    # 3,3: white, 4,4: white, 3,4: black, 4,3: black
    # Valid moves for black: (2,3), (3,2), (4,5), (5,4)
    print("\n--- 2. Making a move (Black: 2,3) ---")
    move_data = {
        "game_id": game_id,
        "row": 2,
        "col": 3,
        "player": "black"
    }
    
    response = requests.post(f"{BASE_URL}/movimiento", json=move_data)
    if response.status_code == 200:
        game_state = response.json()
        print("Move successful!")
        print(f"New score: {game_state['score']}")
        print(f"Current player: {game_state['current_player']}")
        
        if game_state['last_move']:
            lm = game_state['last_move']
            print(f"Last move (should be AI if it moved): {lm['row']},{lm['col']}")
    else:
        print(f"Move failed: {response.status_code} - {response.text}")

    # 3. List valid moves for next turn
    print("\n--- 3. Valid moves for next turn ---")
    if game_state['valid_moves']:
        print(f"Valid moves count: {len(game_state['valid_moves'])}")
        # print first 5
        for m in game_state['valid_moves'][:5]:
            print(f"- ({m['row']}, {m['col']})")
    else:
        print("No valid moves available or game over.")

if __name__ == "__main__":
    test_game_flow()
