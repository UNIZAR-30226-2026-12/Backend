"""
TEST SUITE: HABILIDADES (SKILLS)
=========================================================
Cubre los casos de uso, efectos en tablero y consumo de 
turnos de las 12 habilidades especiales.
"""

import asyncio
import websockets
import requests
import json
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

BASE_URL = "http://localhost:8081"
WS_URL   = "ws://localhost:8081"

# ─────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────

def step(n, msg): print(f"\n[PASO {n}] {msg}")
def ok(msg): print(f"         ✓ OK: {msg}")
def debug(msg): print(f"         · DEBUG: {msg}")

def create_and_login(username, password="password123"):
    email = f"{username}@test.com"
    requests.post(f"{BASE_URL}/api/auth/register", json={"username": username, "email": email, "password": password})
    res_login = requests.post(f"{BASE_URL}/api/auth/login", data={"username": email, "password": password})
    return res_login.json()["access_token"]

def create_game_and_join(creator_token, guest_tokens, mode="1v1_skills"):
    res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {creator_token}"}, json={"mode": mode})
    game_id = res.json()["game_id"]
    for t in guest_tokens:
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t}"})
    return game_id

def delete_user(token, username):
    requests.delete(f"{BASE_URL}/api/users/me", headers={"Authorization": f"Bearer {token}"})

async def safe_recv(ws, timeout=3.0):
    try:
        msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
        return json.loads(msg)
    except asyncio.TimeoutError:
        return None

def print_ascii_board(board, size=8):
    print(f"\n      " + " ".join([str(i) for i in range(size)]))
    print("    +" + "-"*(size*2+1) + "+")
    for r, row in enumerate(board):
        line = f" {r:2} | "
        for cell in row:
            if cell == "black": line += "B "
            elif cell == "white": line += "W "
            elif cell == "red": line += "R "
            elif cell == "blue": line += "U "
            else: line += ". "
        print(line + "|")
    print("    +" + "-"*(size*2+1) + "+\n")


# ─────────────────────────────────────────────
#  BLOQUE 1: LA BOMBA (1v1)
# ─────────────────────────────────────────────

async def run_bomb_1v1_test():
    print("\n" + "="*60)
    print("  BLOQUE 1: HABILIDAD DE BOMBA (1v1)")
    print("="*60)

    u1, u2 = f"bmb1_{uuid.uuid4().hex[:4]}", f"bmb2_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Preparando partida de habilidades entre {u1} y {u2}...")
        t1, t2 = create_and_login(u1), create_and_login(u2)
        game_id = create_game_and_join(t1, [t2], mode="1v1_skills")
        ok("Sala 1v1_skills creada")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
            
            for _ in range(3): 
                await safe_recv(ws1, timeout=0.5)
                await safe_recv(ws2, timeout=0.5)

            step(2, "Dando 'Ready' a ambos jugadores para arrancar la partida...")
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await asyncio.sleep(0.6); await ws2.send(json.dumps({"action": "set_ready", "ready": True}))
            
            for _ in range(5):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and msg.get("payload", {}).get("status") == "playing": break
            ok("Ambos listos. Partida en curso.")

            step(3, "Forzando tablero realista a mitad de partida y dando la bomba a negras...")
            test_board = [[None]*8 for _ in range(8)]
            black_pos = [(0,4),(1,5),(2,1),(2,4),(3,0),(3,4),(3,6),(4,3),(5,6),(6,2),(6,5),(7,4)]
            white_pos = [(1,2),(1,3),(2,2),(2,3),(3,2),(3,3),(3,5),(4,2),(4,4),(4,5),(5,3),(5,4),(5,5)]
            for r, c in black_pos: test_board[r][c] = "black"
            for r, c in white_pos: test_board[r][c] = "white"

            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "debug_force_state", "board": test_board, "current_player": "black"}))
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "bomb"}))

            state_pre = None
            for _ in range(10):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and "bomb" in msg.get("payload", {}).get("skills_inventory", {}).get("black", []):
                    state_pre = msg; break

            assert state_pre is not None, "Nunca se recibio el estado inicial con la bomba inyectada"
            print("\n  [TABLERO ANTES DE LA BOMBA (1v1)]")
            print_ascii_board(state_pre["payload"]["board"])

            step(4, "Negras detonan bomba en (4,3) — su pieza en zona de blancos...")
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "use_skill", "type": "bomb", "row": 4, "col": 3}))

            # Buscamos la respuesta comprobando que la bomba se ha gastado del inventario
            state_post = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg["payload"].get("skills_inventory", {}).get("black", [])
                    if "bomb" not in inv:
                        state_post = msg; break

            assert state_post is not None, "El tablero no se actualizo tras lanzar la bomba"
            board_post = state_post["payload"]["board"]
            print("\n  [TABLERO DESPUES DE LA BOMBA (1v1)]")
            print_ascii_board(board_post)

            # Fichas blancas dentro del radio (3x3 de (4,3)) -> negro
            assert board_post[3][2] == "black", f"(3,2) blanca->negra pero es {board_post[3][2]}"
            assert board_post[3][3] == "black", f"(3,3) blanca->negra pero es {board_post[3][3]}"
            assert board_post[4][2] == "black", f"(4,2) blanca->negra pero es {board_post[4][2]}"
            assert board_post[5][3] == "black", f"(5,3) blanca->negra pero es {board_post[5][3]}"
            # Ficha negra propia en el centro de la bomba -> blanca
            assert board_post[4][3] == "white", f"(4,3) propia->blanca pero es {board_post[4][3]}"
            # Fichas fuera del radio sin cambio
            assert board_post[0][4] == "black",  f"(0,4) fuera del radio sigue negra"
            assert board_post[5][5] == "white",  f"(5,5) fuera del radio sigue blanca"
            assert board_post[1][2] == "white",  f"(1,2) fuera del radio sigue blanca"
            ok("La bomba invirtió fichas en el radio 3x3 y respeto las exteriores")
            
            step(5, "Verificar que el rival no puede usar una bomba que no tiene...")
            while await safe_recv(ws2, timeout=0.2): pass # Limpiamos basura del ws2
            
            await asyncio.sleep(0.6); await ws2.send(json.dumps({"action": "use_skill", "type": "bomb", "row": 0, "col": 0}))
            err2 = None
            for _ in range(10):
                msg = await safe_recv(ws2, timeout=1.0)
                if msg and msg.get("type") == "error":
                    err2 = msg; break

            assert err2 is not None, "El servidor permitio usar habilidad al rival"
            assert "No tienes" in err2["payload"]["message"], "Mensaje de error incorrecto"
            ok("El servidor protege los inventarios correctamente.")

        print("\n  ✔ BLOQUE 1 PASADO: Habilidad de Bomba 1v1 OK")
        return True

    except Exception as e:
        print(f"\n  ✘ BLOQUE 1 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 2: LA BOMBA (4P - REGLA DE RESCATE)
# ─────────────────────────────────────────────

async def run_bomb_4p_test():
    print("\n" + "="*60)
    print("  BLOQUE 2: HABILIDAD DE BOMBA (4P - CASTIGO AL MENOR)")
    print("="*60)

    users = [f"p{i}_{uuid.uuid4().hex[:4]}" for i in range(4)]
    tokens = []

    try:
        step(1, "Preparando partida 4P (16x16) con 4 jugadores...")
        tokens = [create_and_login(u) for u in users]
        game_id = create_game_and_join(tokens[0], tokens[1:], mode="1v1v1v1_skills")
        ok("Sala 1v1v1v1_skills creada")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[0]}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[1]}") as ws2, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[2]}") as ws3, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[3]}") as ws4:
            
            step(2, "Arrancando la partida por WebSocket (forzando ready a todos)...")
            await asyncio.sleep(1.2) # Dejamos que terminen de conectarse las 4 conexiones
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await asyncio.sleep(0.6); await ws2.send(json.dumps({"action": "set_ready", "ready": True}))
            await asyncio.sleep(0.6); await ws3.send(json.dumps({"action": "set_ready", "ready": True}))
            await asyncio.sleep(0.6); await ws4.send(json.dumps({"action": "set_ready", "ready": True}))
            
            state_playing = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and msg.get("payload", {}).get("status") == "playing": 
                    state_playing = msg; break
                    
            assert state_playing is not None, "La partida no llego a estado 'playing'"
            ok("Partida 4P en curso.")

            step(3, "Forzando tablero 4P realista con Rojo como jugador más débil...")
            test_board = [[None]*16 for _ in range(16)]
            black_pos_4p = [
                (0,1),(0,2),(0,3),(1,1),(1,2),(1,3),(1,4),
                (2,1),(2,2),(2,3),(2,4),(2,5),
                (3,2),(3,3),(3,4),(4,2),(4,3),(4,4),
                (5,2),(5,3),(6,2),(6,3),(7,2),(7,3),
                (8,8),  
            ]
            white_pos_4p = [
                (0,10),(0,11),(0,12),(1,10),(1,11),(1,12),(1,13),
                (2,10),(2,11),(2,12),(2,13),(2,14),
                (3,11),(3,12),(3,13),(4,10),(4,11),(4,12),
                (5,10),(5,11),(6,10),(6,11),(7,10),(7,11),
                # zona de bomba: rodean (8,8) por el norte y los lados
                (7,7),(8,7),(8,9),(9,8),
            ]
            blue_pos_4p = [
                # territorio sur-este
                (10,10),(10,11),(10,12),(11,10),(11,11),(11,12),
                (12,10),(12,11),(12,12),(13,11),(13,12),
                (14,11),(14,12),(15,11),(15,12),
                # zona de bomba: dos fichas azules en las esquinas norte del radio
                (7,9),(9,7),
            ]
            red_pos_4p = [
                # solo 4 fichas en el sur-oeste (jugador muy rezagado)
                (13,2),(14,3),(15,2),(15,3),
                # zona de bomba: dos fichas rojas, haciendo el radio de 4 colores
                (7,8),(9,9),
            ]
            for r,c in black_pos_4p: test_board[r][c] = "black"
            for r,c in white_pos_4p: test_board[r][c] = "white"
            for r,c in blue_pos_4p:  test_board[r][c] = "blue"
            for r,c in red_pos_4p:   test_board[r][c] = "red"

            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "debug_force_state", "board": test_board, "current_player": "black"}))
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "bomb"}))
            
            state_pre = None
            for _ in range(10):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and "bomb" in msg.get("payload", {}).get("skills_inventory", {}).get("black", []):
                    state_pre = msg; break

            assert state_pre is not None, "No se recibio el estado con la bomba inyectada"
            print("\n  [TABLERO COMPLETO ANTES DE LA BOMBA (4P, 16x16)]")
            print_ascii_board(state_pre["payload"]["board"], size=16)

            step(4, "Negras detonan bomba en (8,8) — encrucijada de los 4 colores...")
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "use_skill", "type": "bomb", "row": 8, "col": 8}))

            # Buscamos de nuevo basándonos en si la habilidad desapareció del inventario
            state_post = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg["payload"].get("skills_inventory", {}).get("black", [])
                    if "bomb" not in inv:
                        state_post = msg; break

            assert state_post is not None, "El tablero no se actualizo tras lanzar la bomba"
            board_post = state_post["payload"]["board"]
            print("\n  [TABLERO COMPLETO DESPUES DE LA BOMBA (4P, 16x16)]")
            print_ascii_board(board_post, size=16)

            # --- Verificaciones dentro del radio 3x3 de (8,8) ---
            # Fichas blancas vecinas -> negro
            assert board_post[7][7] == "black", f"(7,7) blanca->negra pero es {board_post[7][7]}"
            assert board_post[8][7] == "black", f"(8,7) blanca->negra pero es {board_post[8][7]}"
            assert board_post[8][9] == "black", f"(8,9) blanca->negra pero es {board_post[8][9]}"
            assert board_post[9][8] == "black", f"(9,8) blanca->negra pero es {board_post[9][8]}"
            # Ficha ROJA en el radio -> negro  (verifica que las rojas tambien se convierten)
            assert board_post[7][8] == "black", f"(7,8) roja->negra pero es {board_post[7][8]}"
            assert board_post[9][9] == "black", f"(9,9) roja->negra pero es {board_post[9][9]}"
            # Ficha AZUL en el radio -> negro  (verifica que las azules tambien se convierten)
            assert board_post[7][9] == "black", f"(7,9) azul->negra pero es {board_post[7][9]}"
            assert board_post[9][7] == "black", f"(9,7) azul->negra pero es {board_post[9][7]}"
            # Ficha negra PROPIA en el centro -> rojo (jugador mas debil)
            assert board_post[8][8] == "red",   f"(8,8) propia->roja pero es {board_post[8][8]}"
            # --- Verificaciones fuera del radio: nada cambia ---
            assert board_post[6][2]  == "black", f"(6,2) negra exterior intacta"
            assert board_post[6][10] == "white", f"(6,10) blanca exterior intacta"
            assert board_post[10][10]== "blue",  f"(10,10) azul exterior intacta"
            assert board_post[13][2] == "red",   f"(13,2) roja exterior intacta"
            ok("La bomba convirtió los 3 colores enemigos a negro y cedió el centro a Rojo.")

        print("\n  ✔ BLOQUE 2 PASADO: Habilidad de Bomba 4P OK")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 2 FALLIDO: {e}")
        return False
    finally:
        for t, u in zip(tokens, users):
            if t: delete_user(t, u)


# ─────────────────────────────────────────────
#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────

async def async_main():
    results = {}
    results["Habilidad de Bomba (1v1)"] = await run_bomb_1v1_test()
    results["Habilidad de Bomba (4P)"]  = await run_bomb_4p_test()

    print("\n" + "#"*60)
    print("  RESUMEN FINAL SKILLS")
    print("#"*60)
    passed = sum(1 for v in results.values() if v)
    for nombre, ok_val in results.items():
        print(f"  {'✔ PASS' if ok_val else '✘ FAIL'}  →  {nombre}")
    print(f"\n  Resultado: {passed}/{len(results)} bloques pasados")

if __name__ == "__main__":
    asyncio.run(async_main())