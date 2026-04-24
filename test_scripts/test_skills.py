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

HTTP = requests.Session()
HTTP.trust_env = False

# ─────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────

def step(n, msg): print(f"\n[PASO {n}] {msg}")
def ok(msg): print(f"         ✓ OK: {msg}")
def debug(msg): print(f"         · DEBUG: {msg}")

def create_and_login(username, password="password123"):
    email = f"{username}@test.com"
    HTTP.post(f"{BASE_URL}/api/auth/register", json={"username": username, "email": email, "password": password})
    res_login = HTTP.post(f"{BASE_URL}/api/auth/login", data={"username": email, "password": password})
    return res_login.json()["access_token"]

def create_game_and_join(creator_token, guest_tokens, mode="1v1_skills"):
    res = HTTP.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {creator_token}"}, json={"mode": mode})
    game_id = res.json()["game_id"]
    for t in guest_tokens:
        HTTP.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t}"})
    return game_id

def delete_user(token, username):
    HTTP.delete(f"{BASE_URL}/api/users/me", headers={"Authorization": f"Bearer {token}"})

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
            await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws2.send(json.dumps({"action": "set_ready", "ready": True}))
            
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

            await ws1.send(json.dumps({"action": "debug_force_state", "board": test_board, "current_player": "black"}))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "bomb"}))

            state_pre = None
            for _ in range(10):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and "bomb" in msg.get("payload", {}).get("skills_inventory", {}).get("black", []):
                    state_pre = msg; break

            assert state_pre is not None, "Nunca se recibio el estado inicial con la bomba inyectada"
            print("\n  [TABLERO ANTES DE LA BOMBA (1v1)]")
            print_ascii_board(state_pre["payload"]["board"])

            step(4, "Negras detonan bomba en (4,3) — su pieza en zona de blancos...")
            await ws1.send(json.dumps({"action": "use_skill", "type": "bomb", "row": 4, "col": 3}))

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
            
            await ws2.send(json.dumps({"action": "use_skill", "type": "bomb", "row": 0, "col": 0}))
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
            await asyncio.sleep(1.2)
            await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws2.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws3.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws4.send(json.dumps({"action": "set_ready", "ready": True}))
            
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
                (7,7),(8,7),(8,9),(9,8),
            ]
            blue_pos_4p = [
                (10,10),(10,11),(10,12),(11,10),(11,11),(11,12),
                (12,10),(12,11),(12,12),(13,11),(13,12),
                (14,11),(14,12),(15,11),(15,12),
                (7,9),(9,7),
            ]
            red_pos_4p = [
                (13,2),(14,3),(15,2),(15,3),
                (7,8),(9,9),
            ]
            for r,c in black_pos_4p: test_board[r][c] = "black"
            for r,c in white_pos_4p: test_board[r][c] = "white"
            for r,c in blue_pos_4p:  test_board[r][c] = "blue"
            for r,c in red_pos_4p:   test_board[r][c] = "red"

            await ws1.send(json.dumps({"action": "debug_force_state", "board": test_board, "current_player": "black"}))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "bomb"}))
            
            state_pre = None
            for _ in range(10):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and "bomb" in msg.get("payload", {}).get("skills_inventory", {}).get("black", []):
                    state_pre = msg; break

            assert state_pre is not None, "No se recibio el estado con la bomba inyectada"
            print("\n  [TABLERO COMPLETO ANTES DE LA BOMBA (4P, 16x16)]")
            print_ascii_board(state_pre["payload"]["board"], size=16)

            step(4, "Negras detonan bomba en (8,8) — encrucijada de los 4 colores...")
            await ws1.send(json.dumps({"action": "use_skill", "type": "bomb", "row": 8, "col": 8}))

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

            assert board_post[7][7] == "black", f"(7,7) blanca->negra pero es {board_post[7][7]}"
            assert board_post[8][7] == "black", f"(8,7) blanca->negra pero es {board_post[8][7]}"
            assert board_post[8][9] == "black", f"(8,9) blanca->negra pero es {board_post[8][9]}"
            assert board_post[9][8] == "black", f"(9,8) blanca->negra pero es {board_post[9][8]}"
            assert board_post[7][8] == "black", f"(7,8) roja->negra pero es {board_post[7][8]}"
            assert board_post[9][9] == "black", f"(9,9) roja->negra pero es {board_post[9][9]}"
            assert board_post[7][9] == "black", f"(7,9) azul->negra pero es {board_post[7][9]}"
            assert board_post[9][7] == "black", f"(9,7) azul->negra pero es {board_post[9][7]}"
            assert board_post[8][8] == "red",   f"(8,8) propia->roja pero es {board_post[8][8]}"
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
#  BLOQUE 3: CORRECCIONES DE FICHAS FIJAS
# ─────────────────────────────────────────────

async def run_fixed_pieces_test():
    print("\n" + "="*60)
    print("  BLOQUE 3: CORRECCIONES DE FICHAS FIJAS")
    print("="*60)

    u1, u2 = f"fx1_{uuid.uuid4().hex[:4]}", f"fx2_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Preparando partida 1v1_skills entre {u1} y {u2}...")
        t1, t2 = create_and_login(u1), create_and_login(u2)
        game_id = create_game_and_join(t1, [t2], mode="1v1_skills")
        ok("Sala 1v1_skills creada")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:

            for _ in range(3):
                await safe_recv(ws1, timeout=0.5)
                await safe_recv(ws2, timeout=0.5)

            step(2, "Ready de ambos jugadores...")
            await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws2.send(json.dumps({"action": "set_ready", "ready": True}))

            for _ in range(8):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and msg.get("payload", {}).get("status") == "playing":
                    break
            ok("Partida en curso.")

            step(3, "Forzando tablero de prueba y otorgando habilidades...")
            test_board = [[None]*8 for _ in range(8)]
            test_board[3][3] = "white"
            test_board[3][4] = "black"
            test_board[4][3] = "black"
            test_board[4][4] = "white"
            test_board[2][3] = "white"
            test_board[2][4] = "white"
            test_board[5][3] = "black"
            test_board[5][4] = "black"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board,
                "current_player": "black",
                "skills_inventory": {"black": [], "white": []}
            }))
            for skill in ["fix_piece", "flip_rival", "swap_colors", "unfix_piece"]:
                await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": skill}))

            state_with_skills = None
            for _ in range(20):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if len(inv) >= 4:
                        state_with_skills = msg
                        break

            assert state_with_skills is not None, "No se recibieron las 4 habilidades en el inventario"
            ok("Tablero y habilidades preparados.")

            # ══════════════════════════════════════════
            # SUB-TEST 3a: Movimientos válidos con ficha fija
            # ══════════════════════════════════════════
            step(4, "[3a] Fijando ficha negra en (3,4) con fix_piece y comprobando valid_moves...")
            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "fix_piece",
                "row": 3, "col": 4
            }))

            state_after_fix = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    fp = msg.get("payload", {}).get("fixed_pieces", [])
                    if [3, 4] in fp:
                        state_after_fix = msg
                        break

            assert state_after_fix is not None, "La ficha fija no aparece en el estado tras fix_piece"

            valid_moves = state_after_fix["payload"].get("valid_moves", [])
            debug(f"valid_moves tras fix_piece en (3,4): {valid_moves}")

            assert [3, 4] in state_after_fix["payload"]["fixed_pieces"], \
                "fixed_pieces no contiene [3, 4]"
            ok("fix_piece aplicado; fixed_pieces propagado al estado del juego correctamente.")

            # ══════════════════════════════════════════
            # SUB-TEST 3d: unfix_piece castigo (tablero SIN fichas fijas temporalmente)
            # ══════════════════════════════════════════
            step(5, "[3d] unfix_piece invalido: debe rechazar sin consumir habilidad...")
            test_board2 = [[None]*8 for _ in range(8)]
            test_board2[3][3] = "white"
            test_board2[3][4] = "black"
            test_board2[4][3] = "black"
            test_board2[4][4] = "white"
            test_board2[2][3] = "white"
            test_board2[2][4] = "white"
            test_board2[5][3] = "black"
            test_board2[5][4] = "black"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board2,
                "current_player": "black",
                "fixed_pieces": [],
                "skills_inventory": {"black": [], "white": []}
            }))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "unfix_piece"}))

            state_clean = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "unfix_piece" in inv:
                        state_clean = msg
                        break

            assert state_clean is not None, "No se recibió el estado limpio con unfix_piece"
            ok("Tablero sin fichas fijas listo. Verificando rechazo controlado...")

            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "unfix_piece",
                "row": 0, "col": 0
            }))

            err_unfix = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "error":
                    err_unfix = msg
                    break

            assert err_unfix is not None, "No se recibió error al usar unfix_piece sin fichas fijas"
            assert "No es una ficha fija" in err_unfix.get("payload", {}).get("message", ""), \
                f"Mensaje de error inesperado: {err_unfix}"

            # Reintentar confirma que la habilidad NO se consumió (si se hubiese consumido: 'No tienes esa habilidad')
            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "unfix_piece",
                "row": 0, "col": 0
            }))

            err_unfix_retry = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "error":
                    err_unfix_retry = msg
                    break

            assert err_unfix_retry is not None, "No se recibió error en el reintento de unfix_piece"
            assert "No es una ficha fija" in err_unfix_retry.get("payload", {}).get("message", ""), \
                f"La habilidad parece haberse consumido indebidamente: {err_unfix_retry}"
            ok("Rechazo correcto: unfix_piece invalido no se consume y mantiene consistencia.")

            # ══════════════════════════════════════════
            # SUB-TEST 3b: flip_rival sobre ficha fija
            # ══════════════════════════════════════════
            step(6, "[3b] flip_rival sobre ficha fija: debe cambiar color pero NO liberar la ficha...")
            test_board3 = [[None]*8 for _ in range(8)]
            test_board3[3][3] = "white"
            test_board3[3][4] = "black"
            test_board3[4][3] = "black"
            test_board3[4][4] = "white"
            test_board3[2][3] = "white"
            test_board3[2][4] = "white"
            test_board3[5][3] = "black"
            test_board3[5][4] = "black"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board3,
                "current_player": "black",
                "fixed_pieces": [[4, 4]],
                "skills_inventory": {"black": [], "white": []}
            }))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "flip_rival"}))

            state_flip_ready = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "flip_rival" in inv:
                        fp = msg.get("payload", {}).get("fixed_pieces", [])
                        if [4, 4] in fp:
                            state_flip_ready = msg
                            break

            assert state_flip_ready is not None, "Estado con flip_rival + ficha fija blanca no recibido"
            ok("Preparado: flip_rival disponible, (4,4) blanca y fija.")

            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "flip_rival",
                "row": 4, "col": 4
            }))

            state_after_flip = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "flip_rival" not in inv:
                        state_after_flip = msg
                        break

            assert state_after_flip is not None, "No se recibió el estado tras flip_rival"
            payload_flip = state_after_flip["payload"]
            board_flip = payload_flip["board"]
            fp_flip = payload_flip.get("fixed_pieces", [])

            assert board_flip[4][4] == "black", \
                f"flip_rival sobre ficha fija: (4,4) debería ser 'black' pero es {board_flip[4][4]}"
            assert [4, 4] in fp_flip, \
                f"flip_rival sobre ficha fija: (4,4) debería seguir en fixed_pieces pero fixed_pieces={fp_flip}"
            ok("flip_rival cambió el color de la ficha fija y la mantuvo como fija. ✓")

            # ══════════════════════════════════════════
            # SUB-TEST 3c: swap_colors respeta fichas fijas
            # ══════════════════════════════════════════
            step(7, "[3c] swap_colors NO debe cambiar el color de las fichas fijas...")
            test_board4 = [[None]*8 for _ in range(8)]
            test_board4[3][3] = "white"
            test_board4[3][4] = "black"
            test_board4[4][3] = "black"
            test_board4[4][4] = "white"
            test_board4[2][3] = "white"
            test_board4[2][4] = "white"
            test_board4[5][3] = "black"
            test_board4[5][4] = "black"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board4,
                "current_player": "black",
                "fixed_pieces": [[3, 4]],
                "skills_inventory": {"black": [], "white": []}
            }))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "swap_colors"}))

            state_swap_ready = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "swap_colors" in inv:
                        fp = msg.get("payload", {}).get("fixed_pieces", [])
                        if [3, 4] in fp:
                            state_swap_ready = msg
                            break

            assert state_swap_ready is not None, "Estado con swap_colors + ficha fija negra no recibido"
            ok("Preparado: swap_colors disponible, (3,4) negra y fija.")

            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "swap_colors",
                "target_player": "white"
            }))

            state_after_swap = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "swap_colors" not in inv:
                        state_after_swap = msg
                        break

            assert state_after_swap is not None, "No se recibió el estado tras swap_colors"
            board_swap = state_after_swap["payload"]["board"]

            assert board_swap[3][4] == "black", \
                f"swap_colors: la ficha fija en (3,4) debería seguir siendo 'black' pero es {board_swap[3][4]}"
            assert board_swap[4][4] == "black", \
                f"swap_colors: (4,4) blanca no-fija debería ser 'black' tras swap pero es {board_swap[4][4]}"
            assert board_swap[3][3] == "black", \
                f"swap_colors: (3,3) blanca no-fija debería ser 'black' tras swap pero es {board_swap[3][3]}"
            ok("swap_colors respetó la ficha fija y solo intercambió las no-fijas. ✓")

            # ══════════════════════════════════════════
            # SUB-TEST 3e: unfix_piece exitoso (happy path)
            # ══════════════════════════════════════════
            step(8, "[3e] unfix_piece exitoso: quitar la fija rival permaneciendo en tablero...")
            test_board5 = [[None]*8 for _ in range(8)]
            test_board5[3][3] = "white"
            test_board5[3][4] = "white"
            test_board5[4][3] = "black"
            test_board5[4][4] = "white"
            test_board5[2][3] = "black"
            test_board5[2][4] = "black"
            test_board5[5][3] = "black"
            test_board5[5][4] = "black"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board5,
                "current_player": "black",
                "fixed_pieces": [[3, 4]],
                "skills_inventory": {"black": [], "white": []}
            }))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "unfix_piece"}))

            state_unfix_ready = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    fp = msg.get("payload", {}).get("fixed_pieces", [])
                    if "unfix_piece" in inv and [3, 4] in fp:
                        state_unfix_ready = msg
                        break

            assert state_unfix_ready is not None, "No se recibió estado con unfix_piece + ficha fija blanca"
            ok("Preparado: unfix_piece disponible, (3,4) blanca y fija.")

            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "unfix_piece",
                "row": 3, "col": 4
            }))

            state_after_unfix_ok = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "unfix_piece" not in inv:
                        state_after_unfix_ok = msg
                        break

            assert state_after_unfix_ok is not None, "No se recibió el estado tras unfix_piece exitoso"
            payload_unfix = state_after_unfix_ok["payload"]
            board_unfix = payload_unfix["board"]
            fp_unfix = payload_unfix.get("fixed_pieces", [])

            assert board_unfix[3][4] == "white", \
                f"unfix_piece: (3,4) debe permanecer 'white' en el tablero, pero es {board_unfix[3][4]}"
            assert [3, 4] not in fp_unfix, \
                f"unfix_piece: (3,4) debe haberse eliminado de fixed_pieces, pero aún está en {fp_unfix}"
            ok("unfix_piece exitoso: ficha permanece en tablero pero ya no es fija. ✓")

            # ══════════════════════════════════════════
            # SUB-TEST 3f: tras unfix, la ficha puede voltearse con make_move normal
            # ══════════════════════════════════════════
            step(9, "[3f] Tras unfix, la ficha (3,4) puede voltearse con make_move normal...")
            test_board6 = [[None]*8 for _ in range(8)]
            test_board6[3][3] = "white"
            test_board6[3][4] = "white"
            test_board6[3][5] = "black"
            test_board6[4][3] = "black"
            test_board6[4][4] = "white"
            test_board6[2][4] = "black"
            test_board6[2][3] = "black"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board6,
                "current_player": "black",
                "fixed_pieces": [],
                "skills_inventory": {"black": [], "white": []}
            }))

            state_ready_for_move = None
            for _ in range(10):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    fp = msg.get("payload", {}).get("fixed_pieces", [])
                    if [3, 4] not in fp:
                        state_ready_for_move = msg
                        break

            assert state_ready_for_move is not None, "No se recibió tablero sin fija para make_move"
            valid_moves_now = state_ready_for_move["payload"].get("valid_moves", [])
            debug(f"valid_moves con (3,4) ya libre: {valid_moves_now}")

            can_play_32 = any(m.get("row") == 3 and m.get("col") == 2 for m in valid_moves_now)
            assert can_play_32, \
                f"(3,2) debería ser válido para negro (voltea (3,3) y (3,4) ya libres), pero valid_moves={valid_moves_now}"

            await ws1.send(json.dumps({"action": "make_move", "row": 3, "col": 2}))

            state_after_move = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    board_now = msg.get("payload", {}).get("board", [])
                    if board_now and board_now[3][2] == "black":
                        state_after_move = msg
                        break

            assert state_after_move is not None, "El movimiento (3,2) no se aceptó"
            board_after_move = state_after_move["payload"]["board"]

            assert board_after_move[3][4] == "black", \
                f"(3,4) ya-no-fija debería ser 'black' tras make_move en (3,2), pero es {board_after_move[3][4]}"
            assert board_after_move[3][3] == "black", \
                f"(3,3) blanca debería ser 'black' tras el volteo, pero es {board_after_move[3][3]}"
            ok("Tras unfix, (3,4) se volteó correctamente con make_move. ✓")

            # ══════════════════════════════════════════
            # SUB-TEST 3g: fix_piece sobre celda rival o vacía es rechazado
            # ══════════════════════════════════════════
            step(10, "[3g] fix_piece sobre celda rival o vacía debe ser rechazada por el servidor...")
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "fix_piece"}))

            state_fix_inv = None
            for _ in range(10):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "fix_piece" in inv:
                        state_fix_inv = msg
                        break

            assert state_fix_inv is not None, "No se recibió estado con fix_piece para el test de rechazo"

            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "fix_piece",
                "row": 3, "col": 3   # blanca = rival de negro
            }))

            error_received = False
            for _ in range(8):
                msg = await safe_recv(ws1, timeout=0.8)
                if msg and msg.get("type") == "error":
                    error_received = True
                    break
                if msg and msg.get("type") == "game_state_update":
                    inv_check = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "fix_piece" not in inv_check:
                        # La habilidad fue consumida: eso es un fallo
                        assert False, "fix_piece sobre celda rival fue aceptado incorrectamente"

            assert error_received, \
                "El servidor debería rechazar fix_piece sobre celda rival con un error, pero no lo hizo"
            ok("fix_piece sobre celda rival fue rechazado correctamente. ✓")

            # Intento 2: fix_piece sobre celda vacía (0,0)
            await ws1.send(json.dumps({
                "action": "use_skill",
                "type": "fix_piece",
                "row": 0, "col": 0   # vacía
            }))

            error_received_empty = False
            for _ in range(8):
                msg = await safe_recv(ws1, timeout=0.8)
                if msg and msg.get("type") == "error":
                    error_received_empty = True
                    break
                if msg and msg.get("type") == "game_state_update":
                    inv_check = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "fix_piece" not in inv_check:
                        assert False, "fix_piece sobre celda vacía fue aceptado incorrectamente"

            assert error_received_empty, \
                "El servidor debería rechazar fix_piece sobre celda vacía con un error, pero no lo hizo"
            ok("fix_piece sobre celda vacía rechazado correctamente. ✓")

        print("\n  ✔ BLOQUE 3 PASADO: Correcciones de Fichas Fijas OK")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 3 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 4: BOMBA RESPETA FICHA FIJA (dentro del radio)
# ─────────────────────────────────────────────

async def run_bomb_respects_fixed_test():
    print("\n" + "="*60)
    print("  BLOQUE 4: BOMBA RESPETA FICHA FIJA DENTRO DEL RADIO")
    print("="*60)

    u1, u2 = f"bf1_{uuid.uuid4().hex[:4]}", f"bf2_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Creando partida 1v1_skills entre {u1} y {u2}...")
        t1, t2 = create_and_login(u1), create_and_login(u2)
        game_id = create_game_and_join(t1, [t2], mode="1v1_skills")
        ok("Sala creada.")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:

            for _ in range(3):
                await safe_recv(ws1, timeout=0.5)
                await safe_recv(ws2, timeout=0.5)

            step(2, "Ready de ambos...")
            await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws2.send(json.dumps({"action": "set_ready", "ready": True}))
            for _ in range(8):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and msg.get("payload", {}).get("status") == "playing":
                    break
            ok("Partida en curso.")

            step(3, "Forzando tablero con ficha FIJA blanca en (4,4) dentro del radio de la bomba...")
            test_board = [[None]*8 for _ in range(8)]
            test_board[3][3] = "black"
            test_board[3][4] = "black"
            test_board[4][3] = "black"
            test_board[3][5] = "white"
            test_board[4][4] = "white"  # SERÁ FIJA
            test_board[5][3] = "white"
            test_board[5][4] = "white"
            test_board[5][5] = "white"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board,
                "current_player": "black",
                "fixed_pieces": [[4, 4]]   # (4,4) blanca FIJA
            }))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "black", "skill": "bomb"}))

            state_pre = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "bomb" in inv and [4, 4] in msg.get("payload", {}).get("fixed_pieces", []):
                        state_pre = msg
                        break

            assert state_pre is not None, "No se recibió estado con bomba + ficha fija"
            print("\n  [TABLERO ANTES DE LA BOMBA - ficha fija en (4,4)]")
            print_ascii_board(state_pre["payload"]["board"])

            step(4, "Negras lanzan la bomba centrada en (4,4) — donde está la ficha FIJA blanca...")
            await ws1.send(json.dumps({"action": "use_skill", "type": "bomb", "row": 4, "col": 4}))

            state_post = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("black", [])
                    if "bomb" not in inv:
                        state_post = msg
                        break

            assert state_post is not None, "No se recibió estado tras la bomba"
            board_post = state_post["payload"]["board"]
            print("\n  [TABLERO DESPUÉS DE LA BOMBA]")
            print_ascii_board(board_post)

            assert board_post[3][5] == "black", f"(3,5) blanca-no-fija debería ser 'black' pero es {board_post[3][5]}"
            assert board_post[5][3] == "black", f"(5,3) blanca-no-fija debería ser 'black' pero es {board_post[5][3]}"
            assert board_post[5][4] == "black", f"(5,4) blanca-no-fija debería ser 'black' pero es {board_post[5][4]}"
            assert board_post[5][5] == "black", f"(5,5) blanca-no-fija debería ser 'black' pero es {board_post[5][5]}"

            assert board_post[4][4] == "white", \
                f"(4,4) es FIJA blanca: la bomba NO debe afectarla, pero es {board_post[4][4]}"
            ok("La bomba NO afectó la ficha fija dentro del radio. ✓")

            assert board_post[3][3] == "white", \
                f"(3,3) negra propia en radio debería ser 'white' pero es {board_post[3][3]}"
            ok("Las fichas propias en el radio (no fijas) cambiaron a blanco correctamente. ✓")

        print("\n  ✔ BLOQUE 4 PASADO: Bomba respeta ficha fija OK")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 4 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 5: BOMBA EN MODO vs_ai (IA usa la bomba)
# ─────────────────────────────────────────────

async def run_bomb_vs_ai_test():
    print("\n" + "="*60)
    print("  BLOQUE 5: BOMBA EN MODO vs_ai (IA usa la bomba)")
    print("="*60)

    u1 = f"bai_{uuid.uuid4().hex[:4]}"
    t1 = None

    try:
        step(1, f"Creando partida vs_ai_skills para {u1}...")
        t1 = create_and_login(u1)
        res = HTTP.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "vs_ai_skills"}
        )
        game_id = res.json()["game_id"]
        ok(f"Partida vs_ai_skills creada: {game_id}")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
            for _ in range(5):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and msg.get("payload", {}).get("status") == "playing":
                    break
            ok("Partida vs_ai_skills en curso.")

            step(2, "Forzando tablero y dando bomba a blancas (IA) antes de activar su turno...")
            test_board = [[None]*8 for _ in range(8)]
            black_pos = [(2,3),(2,4),(3,2),(3,5),(4,2),(4,5),(5,2),(5,3),(5,4),(5,5)]
            white_pos = [(3,3),(3,4),(4,3),(4,4),(6,3),(6,4)]
            for r, c in black_pos: test_board[r][c] = "black"
            for r, c in white_pos: test_board[r][c] = "white"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board,
                "current_player": "black",   # negro mueve → check_and_trigger_ai NO activa la IA
                "fixed_pieces": [[3, 2]]
            }))
            await ws1.send(json.dumps({"action": "debug_give_skill", "player": "white", "skill": "bomb"}))

            state_pre = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("white", [])
                    if "bomb" in inv:
                        state_pre = msg
                        break

            assert state_pre is not None, "No se recibió el estado con la bomba en el inventario de la IA"
            print("\n  [TABLERO ANTES DE QUE LA IA USE LA BOMBA]")
            print_ascii_board(state_pre["payload"]["board"])
            ok("Bomba en inventario de IA confirmada.")

            step(3, "Activando turno IA (ya tiene la bomba). El servidor debe usarla automáticamente...")
            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": state_pre["payload"]["board"],
                "current_player": "white",   # ahora sí, turno IA → check_and_trigger_ai dispara
                "fixed_pieces": state_pre["payload"].get("fixed_pieces", [])
            }))

            state_post_ai = None
            for _ in range(20):
                msg = await safe_recv(ws1, timeout=0.5)
                if msg and msg.get("type") == "game_state_update":
                    inv = msg.get("payload", {}).get("skills_inventory", {}).get("white", [])
                    if "bomb" not in inv:
                        state_post_ai = msg
                        break

            assert state_post_ai is not None, \
                "La IA no usó la bomba en el tiempo esperado"
            board_ai = state_post_ai["payload"]["board"]
            print("\n  [TABLERO DESPUÉS DE QUE LA IA USARA LA BOMBA]")
            print_ascii_board(board_ai)
            ok("La IA usó la bomba. ✓")

            step(4, "Verificando que (3,2) negra FIJA NO fue afectada por la bomba de la IA...")
            assert board_ai[3][2] == "black", \
                f"(3,2) negra FIJA: la bomba de la IA NO debe modificarla, pero ahora es {board_ai[3][2]}"
            ok("La bomba de la IA respetó la ficha fija del humano. ✓")

            step(5, "Verificando que el tablero cambió en algún punto (la bomba tuvo efecto)...")
            cells_changed = any(
                board_ai[r][c] == "white"
                for r, c in black_pos
                if (r, c) != (3, 2)  # excluimos la fija
            )
            assert cells_changed, "La bomba de la IA no cambió ninguna ficha negra a blanca"
            ok("La bomba tuvo efecto real en el tablero. ✓")

        print("\n  ✔ BLOQUE 5 PASADO: Bomba en vs_ai OK")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 5 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)


# ─────────────────────────────────────────────
#  BLOQUE 6: fix_piece vs IA (make_move no puede voltear ficha fija)
# ─────────────────────────────────────────────

async def run_fix_piece_vs_ai_test():
    print("\n" + "="*60)
    print("  BLOQUE 6: fix_piece — make_move no voltea ficha fija (vs_ai)")
    print("="*60)

    u1 = f"fva_{uuid.uuid4().hex[:4]}"
    t1 = None

    try:
        step(1, f"Creando partida vs_ai_skills para {u1}...")
        t1 = create_and_login(u1)
        res = HTTP.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "vs_ai_skills"}
        )
        game_id = res.json()["game_id"]
        ok(f"Partida vs_ai_skills creada: {game_id}")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
            for _ in range(5):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update" and msg.get("payload", {}).get("status") == "playing":
                    break
            ok("Partida vs_ai_skills en curso.")

            step(2, "Forzando tablero con ficha FIJA negra en (3,4) y turno de blancas (IA)...")
            test_board = [[None]*8 for _ in range(8)]
            test_board[3][3] = "white"
            test_board[3][4] = "black"
            test_board[3][5] = "white"
            test_board[4][3] = "black"
            test_board[4][4] = "white"
            test_board[5][3] = "black"
            test_board[5][4] = "black"
            test_board[2][4] = "black"
            test_board[2][3] = "white"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": test_board,
                "current_player": "white",
                "fixed_pieces": [[3, 4]]
            }))

            state_pre = None
            for _ in range(15):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    fp = msg.get("payload", {}).get("fixed_pieces", [])
                    if [3, 4] in fp and msg.get("payload", {}).get("current_player") == "white":
                        state_pre = msg
                        break

            assert state_pre is not None, "No se recibió el estado con ficha fija antes del turno IA"
            print("\n  [TABLERO ANTES DEL TURNO DE LA IA — (3,4) negra FIJA]")
            print_ascii_board(state_pre["payload"]["board"])
            ok("Estado previo verificado: (3,4) negra y fija.")

            step(3, "La IA ejecuta su turno (máx. 4 segundos). Verificando que (3,4) no cambia...")
            state_after_ai = None
            for _ in range(20):
                msg = await safe_recv(ws1, timeout=0.5)
                if msg and msg.get("type") == "game_state_update":
                    payload = msg.get("payload", {})
                    if payload.get("current_player") == "black" or payload.get("last_move"):
                        state_after_ai = msg
                        break

            assert state_after_ai is not None, "La IA no hizo ningún movimiento en el tiempo esperado"
            board_after = state_after_ai["payload"]["board"]
            fp_after = state_after_ai["payload"].get("fixed_pieces", [])
            print("\n  [TABLERO DESPUÉS DEL TURNO DE LA IA]")
            print_ascii_board(board_after)

            assert board_after[3][4] == "black", \
                f"(3,4) era FIJA negra: la IA no debería haberla volteado, pero ahora es {board_after[3][4]}"
            ok("La IA no pudo voltear la ficha fija negra con make_move. ✓")

            assert [3, 4] in fp_after, \
                f"(3,4) debería seguir en fixed_pieces después del turno IA, pero fixed_pieces={fp_after}"
            ok("fixed_pieces intacto después del turno de la IA. ✓")

        print("\n  ✔ BLOQUE 6 PASADO: fix_piece resiste el turno de la IA OK")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 6 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)


# ─────────────────────────────────────────────
#  BLOQUE 7: IA ignora skill invalida (vs_ai)
# ─────────────────────────────────────────────

async def run_ai_invalid_skill_fallback_vs_ai_test():
    print("\n" + "="*60)
    print("  BLOQUE 7: IA ignora skill invalida y mueve normal (vs_ai)")
    print("="*60)

    u1 = f"ais1_{uuid.uuid4().hex[:4]}"
    t1 = None

    try:
        step(1, f"Creando partida vs_ai_skills para {u1}...")
        t1 = create_and_login(u1)
        res = HTTP.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "vs_ai_skills"}
        )
        game_id = res.json()["game_id"]
        ok(f"Partida vs_ai_skills creada: {game_id}")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
            for _ in range(6):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    break

            step(2, "Forzando turno de IA con skill invalida (steal_skill sin inventario rival)...")
            board = [[None]*8 for _ in range(8)]
            board[3][3] = "white"
            board[3][4] = "black"
            board[4][3] = "black"
            board[4][4] = "white"

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": board,
                "current_player": "white",
                "fixed_pieces": [],
                "skills_inventory": {"black": [], "white": ["steal_skill"]}
            }))

            state_after_ai = None
            for _ in range(20):
                msg = await safe_recv(ws1, timeout=0.5)
                if not msg or msg.get("type") != "game_state_update":
                    continue
                payload = msg.get("payload", {})
                if payload.get("current_player") == "black" and payload.get("last_move"):
                    state_after_ai = payload
                    break

            assert state_after_ai is not None, "La IA no hizo movimiento normal tras skill invalida"
            assert "steal_skill" in state_after_ai.get("skills_inventory", {}).get("white", []), \
                "La skill invalida no deberia consumirse"
            ok("La IA ignora skill invalida y realiza movimiento normal en vs_ai.")

        print("\n  ✔ BLOQUE 7 PASADO: fallback IA en vs_ai OK")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 7 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)


# ─────────────────────────────────────────────
#  BLOQUE 8: IA ignora skill invalida (4P)
# ─────────────────────────────────────────────

async def run_ai_invalid_skill_fallback_4p_test():
    print("\n" + "="*60)
    print("  BLOQUE 8: IA ignora skill invalida y mueve normal (4P)")
    print("="*60)

    u1 = f"ais4_{uuid.uuid4().hex[:4]}"
    t1 = None

    try:
        step(1, f"Creando partida 4P skills con bots para {u1}...")
        t1 = create_and_login(u1)
        res = HTTP.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "1v1v1v1_skills"}
        )
        game_id = res.json()["game_id"]

        for _ in range(3):
            rb = HTTP.post(
                f"{BASE_URL}/api/games/{game_id}/add_bot",
                headers={"Authorization": f"Bearer {t1}"}
            )
            assert rb.status_code == 200, f"No se pudo añadir bot: {rb.status_code} {rb.text}"

        ok(f"Partida 4P skills creada y rellenada con bots: {game_id}")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
            latest_payload = None
            for _ in range(20):
                msg = await safe_recv(ws1, timeout=1.0)
                if msg and msg.get("type") == "game_state_update":
                    latest_payload = msg.get("payload", {})
                    if latest_payload.get("status") == "playing":
                        break

            assert latest_payload is not None, "No se recibio estado inicial 4P"
            username_by_piece = latest_payload.get("username_by_piece", {})
            ai_piece = next((p for p, u in username_by_piece.items() if isinstance(u, str) and u.startswith("IA_")), None)
            assert ai_piece is not None, "No se detecto pieza IA en 4P"

            step(2, f"Forzando turno IA ({ai_piece}) con steal_skill invalida...")
            skills_inventory = {"black": [], "white": [], "red": [], "blue": []}
            skills_inventory[ai_piece] = ["steal_skill"]

            await ws1.send(json.dumps({
                "action": "debug_force_state",
                "board": latest_payload.get("board"),
                "current_player": ai_piece,
                "fixed_pieces": latest_payload.get("fixed_pieces", []),
                "skills_inventory": skills_inventory
            }))

            state_after_ai = None
            for _ in range(30):
                msg = await safe_recv(ws1, timeout=0.5)
                if not msg or msg.get("type") != "game_state_update":
                    continue
                payload = msg.get("payload", {})
                if payload.get("current_player") != ai_piece and payload.get("last_move"):
                    state_after_ai = payload
                    break

            assert state_after_ai is not None, "La IA 4P no hizo movimiento normal tras skill invalida"
            assert "steal_skill" in state_after_ai.get("skills_inventory", {}).get(ai_piece, []), \
                "La skill invalida no deberia consumirse en 4P"
            ok("La IA ignora skill invalida y realiza movimiento normal en 4P.")

        print("\n  ✔ BLOQUE 8 PASADO: fallback IA en 4P OK")
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 8 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)


# ─────────────────────────────────────────────
#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────

async def async_main():
    results = {}
    results["Habilidad de Bomba (1v1)"]          = await run_bomb_1v1_test()
    results["Habilidad de Bomba (4P)"]            = await run_bomb_4p_test()
    results["Correcciones Fichas Fijas"]          = await run_fixed_pieces_test()
    results["Bomba respeta ficha fija (radio)"]   = await run_bomb_respects_fixed_test()
    results["Bomba en modo vs_ai"]                = await run_bomb_vs_ai_test()
    results["fix_piece resiste turno IA (vs_ai)"] = await run_fix_piece_vs_ai_test()
    results["IA fallback skill invalida (vs_ai)"] = await run_ai_invalid_skill_fallback_vs_ai_test()
    results["IA fallback skill invalida (4P)"]    = await run_ai_invalid_skill_fallback_4p_test()

    print("\n" + "#"*60)
    print("  RESUMEN FINAL SKILLS")
    print("#"*60)
    passed = sum(1 for v in results.values() if v)
    for nombre, ok_val in results.items():
        print(f"  {'✔ PASS' if ok_val else '✘ FAIL'}  →  {nombre}")
    print(f"\n  Resultado: {passed}/{len(results)} bloques pasados")

if __name__ == "__main__":
    asyncio.run(async_main())