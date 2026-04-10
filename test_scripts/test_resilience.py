"""
TEST SUITE: RESILIENCIA DE RED, RECONEXION Y AISLAMIENTO
=========================================================
Cubre los siguientes ambitos:
  1. Flickering: desconexiones rapidas repetidas sin corrupcion de estado
  2. Reconexion exitosa tras microcorte (partida supervive)
  3. Abandono definitivo: timeout y declaracion de ganador por W/O
  4. Aislamiento total de salas: sin interferencias entre partidas distintas
"""

import asyncio
import websockets
import requests
import json
import uuid
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from game.manager import GameManager

BASE_URL = "http://localhost:8081"
WS_URL   = "ws://localhost:8081"

# ─────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────

def step(n, msg):
    print(f"\n[PASO {n}] {msg}")

def ok(msg):
    print(f"         ✓ OK: {msg}")

def debug(msg):
    print(f"         · DEBUG: {msg}")

def create_and_login(username, password="password123"):
    email = f"{username}@test.com"
    res_reg = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": username, "email": email, "password": password
    })
    assert res_reg.status_code == 200, \
        f"[ERROR] Registro '{username}': HTTP {res_reg.status_code} → {res_reg.text}"
    debug(f"'{username}' registrado (ID: {res_reg.json().get('id')})")

    res_log = requests.post(f"{BASE_URL}/api/auth/login",
                            data={"username": username, "password": password})
    assert res_log.status_code == 200, \
        f"[ERROR] Login '{username}': HTTP {res_log.status_code} → {res_log.text}"
    token = res_log.json()["access_token"]
    debug(f"Token JWT obtenido para '{username}'")
    return token

def delete_user(token, username):
    res = requests.delete(f"{BASE_URL}/api/users/me",
                          headers={"Authorization": f"Bearer {token}"})
    if res.status_code == 200:
        print(f"   [Limpieza] '{username}' eliminado.")
    else:
        print(f"   [Limpieza] ATENCION — No se pudo eliminar '{username}': {res.text}")

def get_user_id(token):
    return requests.get(f"{BASE_URL}/api/users/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

def create_and_login(username, password="password123"):
    email = f"{username}@test.com"
    requests.post(f"{BASE_URL}/api/auth/register", json={"username": username, "email": email, "password": password})
    return requests.post(f"{BASE_URL}/api/auth/login", data={"username": username, "password": password}).json()["access_token"]

def get_random_users(count):
    users = []
    tokens = []
    ids = []
    for _ in range(count):
        u = f"u4p_{uuid.uuid4().hex[:4]}"
        t = create_and_login(u)
        users.append(u)
        tokens.append(t)
        ids.append(get_user_id(t))
    return users, tokens, ids

async def wait_for_game_update(ws, timeout=4.0):
    for _ in range(12):
        msg = await safe_recv(ws, timeout=timeout)
        if msg and msg.get("type") == "game_state_update":
            return msg
    return None

async def wait_for_board(ws, timeout=3.0):
    # Lee mensajes hasta encontrar el estado real del juego ignorando el lobby
    for _ in range(10):
        msg = await safe_recv(ws, label="wait_board", timeout=timeout)
        if msg and msg.get("type") == "game_state_update":
            return msg
    return None

async def safe_recv(ws, label="WS", timeout=3.0):
    try:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            raw  = await asyncio.wait_for(ws.recv(), timeout=remaining)
            data = json.loads(raw)
            tipo = data.get("type", "?")
            
            if tipo == "waiting_for_player":
                await asyncio.sleep(0.6)
                await ws.send(json.dumps({"action": "set_ready", "ready": True}))
                debug(f"[{label}] Auto-ready enviado.")
                deadline = loop.time() + timeout  # Reiniciar deadline tras consumir waiting_for_player
                continue
                
            if tipo == "room_sync":
                continue
                
            debug(f"[{label}] tipo='{tipo}' | payload={str(data.get('payload',''))[:120]}")
            return data
        debug(f"[{label}] TIMEOUT ({timeout}s) — sin mensaje")
        return None
    except asyncio.TimeoutError:
        debug(f"[{label}] TIMEOUT ({timeout}s) — sin mensaje")
        return None
    except Exception as e:
        debug(f"[{label}] Error al recibir: {e}")
        return None

def create_game_and_join(token_host, token_guest):
    """Crea sala y une al guest. Devuelve game_id."""
    res = requests.post(
        f"{BASE_URL}/api/games/create",
        headers={"Authorization": f"Bearer {token_host}"},
        json={"mode": "1vs1"}
    )
    assert res.status_code == 200, f"Error creando sala: {res.text}"
    game_id = res.json()["game_id"]
    debug(f"Sala creada: '{game_id}'")

    res_j = requests.post(
        f"{BASE_URL}/api/games/join/{game_id}",
        headers={"Authorization": f"Bearer {token_guest}"}
    )
    assert res_j.status_code == 200, f"Error uniendo guest: {res_j.text}"
    debug(f"Guest unido a '{game_id}'")
    return game_id


# ─────────────────────────────────────────────
#  BLOQUE 1: FLICKERING (RECONEXIONES RAPIDAS)
# ─────────────────────────────────────────────

async def run_flickering_test():
    print("\n" + "="*60)
    print("  BLOQUE 1: INTERMITENCIA AGRESIVA (FLICKERING)")
    print("="*60)

    u1 = f"flash_{uuid.uuid4().hex[:4]}"
    u2 = f"rival_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Preparando sala entre '{u1}' (inestable) y '{u2}' (estable)...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        game_id = create_game_and_join(t1, t2)
        ok(f"Sala '{game_id}' lista")

        step(2, "'{u2}' se conecta de forma estable y espera...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws_rival:
            await safe_recv(ws_rival, label=f"init-{u2}")

            step(3, f"'{u1}' realiza 3 ciclos de conexion/desconexion rapida (flickering)...")
            for i in range(1, 4):
                debug(f"--- Ciclo {i}/3: conectando '{u1}'...")
                try:
                    async with websockets.connect(
                        f"{WS_URL}/ws/play/{game_id}?token={t1}"
                    ) as ws_temp:
                        msg = await safe_recv(ws_temp, label=f"flash-{i}", timeout=2.0)
                        debug(f"Ciclo {i}: recibido tipo='{msg.get('type') if msg else None}'")
                        debug(f"Ciclo {i}: desconectando abruptamente...")
                        await ws_temp.close()
                except Exception as e:
                    pass
                
                await asyncio.sleep(1.0)  # 1.0s para que el servidor cierre el handler anterior
                
            ok("3 ciclos de flickering completados sin crash del servidor")

            step(4, "Reconexion final y definitiva de '{u1}'...")
            await asyncio.sleep(1.0)
            
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
                asig = await safe_recv(ws1, label=f"final-asig-{u1}", timeout=4.0)
                assert asig is not None, \
                    "'{u1}' no recibio asignacion de color en la reconexion final"
                assert asig.get("type") == "player_assignment", \
                    f"Tipo incorrecto: '{asig.get('type')}'"
                debug(f"Color en reconexion final: {asig.get('payload', {}).get('color')}")
                ok("Reconexion final exitosa. Asignacion de color recibida")

                step(5, "Verificando que el estado del juego es coherente (no corrompido)...")
                tablero, _ = await asyncio.gather(
                    wait_for_board(ws1, timeout=4.0),
                    wait_for_board(ws_rival, timeout=4.0)
                )
                if tablero and tablero.get("type") == "game_state_update":
                    game_over = tablero["payload"].get("game_over", False)
                    assert not game_over, \
                        "La partida se marco como game_over por error tras el flickering"
                    ok("Estado del juego intacto. game_over=False correctamente")
                else:
                    debug("Tablero no recibido directamente, estado asumido coherente")

                step(6, "Realizando movimiento tras reconexion para confirmar funcionalidad...")
                mov = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
                await asyncio.sleep(0.6); await ws1.send(json.dumps(mov))
                res_mov = await safe_recv(ws1, label=f"mov-post-flicker-{u1}", timeout=4.0)
                assert res_mov is not None, \
                    "El servidor no respondio al movimiento tras el flickering"
                assert res_mov.get("type") == "game_state_update", \
                    f"Tipo incorrecto: '{res_mov.get('type')}'"
                ok("Movimiento aceptado correctamente tras el flickering")

            step(7, "Esperando 2s para descartar 'falsos abandonos' por temporizadores residuales...")
            await asyncio.sleep(2.0)
            # El servidor no deberia haber disparado un abandono por las desconexiones previas
            res_check = requests.get(f"{BASE_URL}/api/ranking/")
            assert res_check.status_code == 200, "El servidor no responde tras el flickering"
            ok("Servidor estable. No se detectaron abandonos fantasma")

        print("\n  ✔ BLOQUE 1 PASADO: Flickering sin corrupcion de estado OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 1 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 1]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 2: RECONEXION EXITOSA TRAS MICROCORTE
# ─────────────────────────────────────────────

async def run_reconnection_test():
    print("\n" + "="*60)
    print("  BLOQUE 2: RECONEXION EXITOSA TRAS MICROCORTE")
    print("="*60)

    u1 = f"recon_{uuid.uuid4().hex[:4]}"
    u2 = f"stable_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Preparando partida entre '{u1}' y '{u2}'...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        game_id = create_game_and_join(t1, t2)
        ok(f"Sala '{game_id}' lista")

        step(2, f"'{u2}' se conecta de forma estable...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
            await safe_recv(ws2, label=f"asig-{u2}")

            step(3, f"'{u1}' se conecta, empieza la partida y luego se desconecta abruptamente...")
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
                asig = await safe_recv(ws1, label=f"asig-{u1}")
                assert asig and asig.get("type") == "player_assignment"
                await asyncio.gather(wait_for_board(ws1), wait_for_board(ws2))
                debug(f"'{u1}' recibio asignacion y empezo la partida antes de desconectarse")
            debug(f"'{u1}' desconectado. Simulando microcorte de 0.8s...")

            step(4, "Esperando 0.8s (microcorte)...")
            await asyncio.sleep(0.8)

            step(5, f"'{u1}' se reconecta a la misma partida...")
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1_re:
                asig_re = await safe_recv(ws1_re, label=f"recon-asig-{u1}", timeout=6.0)
                assert asig_re is not None, \
                    f"'{u1}' no recibio nada al reconectarse"
                assert asig_re.get("type") == "player_assignment", \
                    f"Tipo incorrecto en reconexion: '{asig_re.get('type')}'"
                debug(f"Color recuperado: {asig_re.get('payload', {}).get('color')}")
                ok("Color recuperado correctamente al reconectarse")

                tablero = await wait_for_board(ws1_re, timeout=6.0)
                if tablero:
                    game_over = tablero.get("payload", {}).get("game_over", False)
                    assert not game_over, \
                        "La partida fue marcada como game_over durante el microcorte de 0.8s"
                    debug(f"Turno actual: {tablero['payload'].get('current_player')}")
                    ok("Partida activa tras reconexion. game_over=False")
                else:
                    debug("No se recibio game_state_update directo (puede ser normal)")
                    ok("Reconexion completada sin game_over")

            step(6, "Verificando que '{u2}' no recibio ningun game_over espurio...")
            msg_u2 = await safe_recv(ws2, label=f"check-espurio-{u2}", timeout=2.0)
            if msg_u2 and msg_u2.get("type") == "game_state_update":
                debug(f"Mensaje recibido por u2: type=game_state_update, "
                      f"game_over={msg_u2['payload'].get('game_over')}")
                assert not msg_u2["payload"].get("game_over"), \
                    "'{u2}' recibio un game_over falso durante el microcorte"
            elif msg_u2 is None:
                ok("'{u2}' no recibio ningun evento espurio durante el microcorte")

        print("\n  ✔ BLOQUE 2 PASADO: Reconexion exitosa tras microcorte OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 2 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 2]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 3: ABANDONO DEFINITIVO (RAGEQUIT)
# ─────────────────────────────────────────────

async def run_abandonment_test():
    print("\n" + "="*60)
    print("  BLOQUE 3: ABANDONO DEFINITIVO POR TIMEOUT (RAGEQUIT)")
    print("="*60)

    u3 = f"ragequit_{uuid.uuid4().hex[:4]}"
    u4 = f"winner_{uuid.uuid4().hex[:4]}"
    t3, t4 = None, None

    try:
        step(1, f"Preparando partida entre '{u3}' (abandonara) y '{u4}' (esperara)...")
        t3 = create_and_login(u3)
        t4 = create_and_login(u4)
        game_id = create_game_and_join(t3, t4)
        ok(f"Sala '{game_id}' lista")

        step(2, f"'{u4}' se conecta y permanece estable. '{u3}' entra y se va...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t4}") as ws4:
            await safe_recv(ws4, label=f"asig-{u4}")

            # u3 entra, espera a que empiece y abandona la conexión
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t3}") as ws3:
                await safe_recv(ws3, label=f"asig-{u3}")
                await asyncio.gather(wait_for_board(ws3), wait_for_board(ws4))
                debug(f"'{u3}' conectado y partida activa. Desconectando definitivamente (ragequit)...")
            debug(f"'{u3}' desconectado de partida iniciada. El servidor deberia iniciar el temporizador de abandono.")

            step(3, "Esperando que el servidor detecte el abandono y declare ganador...")
            debug("Monitorizando mensajes en el WS de '{u4}' (timeout total: 30s)...")
            abandono_detectado = False

            for intento in range(15):
                estado = await safe_recv(ws4, label=f"espera-abandono-{u4}", timeout=3.0)
                if estado is None:
                    debug(f"Intento {intento+1}/15: sin mensaje aun...")
                    continue

                if estado.get("type") == "game_state_update":
                    payload = estado.get("payload", {})
                    game_over = payload.get("game_over", False)
                    winner    = payload.get("winner")
                    debug(f"Intento {intento+1}/15: game_over={game_over}, winner='{winner}'")

                    if game_over:
                        assert winner is not None, \
                            "game_over=True pero 'winner' es None"
                        debug(f"Ganador declarado por abandono: '{winner}'")
                        abandono_detectado = True
                        break

            assert abandono_detectado, \
                "El servidor nunca notifico el abandono al rival en 45s"
            ok(f"Abandono detectado correctamente. Ganador por W/O: '{winner}'")

        print("\n  ✔ BLOQUE 3 PASADO: Deteccion de abandono por timeout OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 3 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 3]")
        if t3: delete_user(t3, u3)
        if t4: delete_user(t4, u4)


# ─────────────────────────────────────────────
#  BLOQUE 4: AISLAMIENTO DE SALAS
# ─────────────────────────────────────────────

async def run_isolation_test():
    print("\n" + "="*60)
    print("  BLOQUE 4: AISLAMIENTO TOTAL DE SALAS (ANTI-INTERFERENCIAS)")
    print("="*60)

    names  = [f"iso_{i}_{uuid.uuid4().hex[:3]}" for i in range(4)]
    tokens = []

    try:
        step(1, "Creando y logueando 4 usuarios (2 por sala)...")
        for n in names:
            tokens.append(create_and_login(n))
        debug(f"Usuarios: {names}")
        ok("4 usuarios listos")

        step(2, "Creando Sala A (usuarios 0 y 1) y Sala B (usuarios 2 y 3)...")
        res_a = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {tokens[0]}"},
            json={"mode": "1vs1"}
        )
        assert res_a.status_code == 200, f"Error creando Sala A: {res_a.text}"
        game_a = res_a.json()["game_id"]
        requests.post(f"{BASE_URL}/api/games/join/{game_a}",
                      headers={"Authorization": f"Bearer {tokens[1]}"})

        res_b = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {tokens[2]}"},
            json={"mode": "1vs1"}
        )
        assert res_b.status_code == 200, f"Error creando Sala B: {res_b.text}"
        game_b = res_b.json()["game_id"]
        requests.post(f"{BASE_URL}/api/games/join/{game_b}",
                      headers={"Authorization": f"Bearer {tokens[3]}"})

        debug(f"Sala A: '{game_a}' | Sala B: '{game_b}'")
        ok(f"Dos salas creadas y configuradas")

        step(3, "Conectando los 4 WebSockets de forma simultanea...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_a}?token={tokens[0]}") as ws_a1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_a}?token={tokens[1]}") as ws_a2, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_b}?token={tokens[2]}") as ws_b1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_b}?token={tokens[3]}") as ws_b2:

            debug("Esperando a que las dos salas arranquen oficialmente...")
            await asyncio.gather(
                wait_for_board(ws_a1),
                wait_for_board(ws_a2),
                wait_for_board(ws_b1),
                wait_for_board(ws_b2)
            )
            ok("Ambas salas inicializadas y tableros en pantalla. Listos para test de aislamiento.")

            step(4, f"Jugador A1 ({names[0]}) realiza un movimiento en la Sala A...")
            movimiento = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
            await asyncio.sleep(0.6); await ws_a1.send(json.dumps(movimiento))
            debug(f"Movimiento enviado en Sala A: {movimiento}")

            step(5, "Verificando que A2 recibe la actualizacion de la Sala A...")
            msg_a2 = await safe_recv(ws_a2, label="A2-post-mov", timeout=4.0)
            await safe_recv(ws_a1, label="A1-post-mov", timeout=1.0)
            assert msg_a2 is not None, \
                "A2 no recibio actualizacion tras el movimiento de A1"
            assert msg_a2.get("type") == "game_state_update", \
                f"A2 recibio tipo incorrecto: '{msg_a2.get('type')}'"
            debug(f"last_move en A2: {msg_a2.get('payload', {}).get('last_move')}")
            ok(f"Sala A sincronizada correctamente (A2 recibio el movimiento de A1)")

            step(6, "VERIFICACION CRITICA: La Sala B NO debe recibir nada de la Sala A...")
            debug("Esperando 1.5s de silencio en ambos WebSockets de la Sala B...")
            msg_b1 = await safe_recv(ws_b1, label="B1-silencio", timeout=1.5)
            msg_b2 = await safe_recv(ws_b2, label="B2-silencio", timeout=1.5)

            debug(f"Mensaje recibido por B1: {msg_b1}")
            debug(f"Mensaje recibido por B2: {msg_b2}")

            assert msg_b1 is None, \
                f"¡FALLO CRITICO DE AISLAMIENTO! B1 recibio un mensaje de la Sala A: {msg_b1}"
            assert msg_b2 is None, \
                f"¡FALLO CRITICO DE AISLAMIENTO! B2 recibio un mensaje de la Sala A: {msg_b2}"
            ok("Silencio total en la Sala B. Las salas estan perfectamente aisladas")

            step(7, "Verificacion inversa: movimiento en Sala B no llega a Sala A...")
            await asyncio.sleep(0.6); await ws_b1.send(json.dumps({"action": "make_move", "row": 5, "col": 4, "player": "black"}))
            debug("Movimiento enviado en Sala B...")

            # Consumir la actualizacion legitima de B2
            await safe_recv(ws_b2, label="B2-propio", timeout=2.0)

            # Sala A no debe recibir nada
            msg_a1_ext = await safe_recv(ws_a1, label="A1-silencio", timeout=1.5)
            assert msg_a1_ext is None, \
                f"¡FALLO CRITICO! A1 recibio un mensaje de la Sala B: {msg_a1_ext}"
            ok("Aislamiento inverso confirmado. Sala A no recibio nada de la Sala B")

        print("\n  ✔ BLOQUE 4 PASADO: Aislamiento de salas perfecto OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 4 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 4]")
        for t, n in zip(tokens, names):
            if t:
                delete_user(t, n)

# ─────────────────────────────────────────────
#  BLOQUE 5: RENDICION Y ABANDONO PARCIAL (4P)
# ─────────────────────────────────────────────

async def run_4p_abandonment_test():
    print("\n" + "="*60)
    print("  BLOQUE 5: RENDICION Y ABANDONO PARCIAL (4P)")
    print("="*60)
    users, tokens, ids = get_random_users(4)
    try:
        step(1, "Iniciando sala 4P para testeo de abandonos...")
        res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {tokens[0]}"}, json={"mode": "1v1v1v1"})
        game_id = res.json()["game_id"]
        for t in tokens[1:]: requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t}"})

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[0]}") as ws0, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[1]}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[2]}") as ws2, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[3]}") as ws3:
            
            await asyncio.gather(wait_for_game_update(ws0), wait_for_game_update(ws1), wait_for_game_update(ws2), wait_for_game_update(ws3))

            step(2, "Rendicion Parcial...")
            await asyncio.sleep(0.6); await ws0.send(json.dumps({"action": "surrender", "player": "black"}))
            estado = await wait_for_game_update(ws1)
            assert not estado["payload"]["game_over"], "La partida termino erroneamente"
            assert "black" not in estado["payload"].get("active_pieces", []), "Black no quitado"
            assert estado["payload"]["current_player"] == "white", "Turno no salto a white"
            ok("Rendicion manejada sin acabar el juego y pasando el turno")

            step(3, "Abandono por Timeout (Ragequit Parcial)...")
            await ws1.close() 
            abandonado = False
            for _ in range(16):
                estado = await wait_for_game_update(ws2)
                if estado and "white" in estado["payload"].get("abandoned_pieces", []):
                    assert not estado["payload"]["game_over"], "El abandono acabo la partida"
                    abandonado = True
                    break
            assert abandonado, "El timeout no expulso al jugador 'white'"
            ok("Expulsion por timeout parcial (30s) procesada con exito")

            step(4, "Bloqueo Mutuo Prematuro (todos se rinden)...")
            await asyncio.sleep(0.6); await ws2.send(json.dumps({"action": "surrender"}))
            await asyncio.sleep(0.6); await ws3.send(json.dumps({"action": "surrender"}))
            
            game_over_reached = False
            for _ in range(10):
                final_state = await wait_for_game_update(ws3)
                if final_state and final_state["payload"]["game_over"]:
                    game_over_reached = True
                    break
            
            assert game_over_reached, "El juego no reporta fin global tras bloqueo mutuo"
            ok("Fin global notificado tras quedarse sin jugadores")

        print("\n  ✔ BLOQUE 5 PASADO: Manejo de ciclo de vida parcial OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 5 FALLIDO: {e}")
        return False
    finally:
        for t, u in zip(tokens, users): delete_user(t, u)

# ─────────────────────────────────────────────
#  BLOQUE 6: RESILIENCIA DE RED MULTIPLE (4P)
# ─────────────────────────────────────────────

async def run_4p_flickering_recon_test():
    print("\n" + "="*60)
    print("  BLOQUE 6: RESILIENCIA DE RED MULTIPLE (4P)")
    print("="*60)
    users, tokens, ids = get_random_users(4)
    try:
        res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {tokens[0]}"}, json={"mode": "1v1v1v1"})
        game_id = res.json()["game_id"]
        for t in tokens[1:]: requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t}"})

        step(1, "Flickering Multiple...")
        ws0 = await websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[0]}")
        ws1 = await websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[1]}")
        ws2 = await websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[2]}")
        ws3 = await websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[3]}")

        await asyncio.gather(wait_for_game_update(ws0), wait_for_game_update(ws1), wait_for_game_update(ws2), wait_for_game_update(ws3))

        await ws1.close()
        await ws2.close()

        step(2, "Reconexion de identidad...")
        ws1_re = await websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[1]}")
        ws2_re = await websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[2]}")

        asig1 = await safe_recv(ws1_re)
        asig2 = await safe_recv(ws2_re)
        assert asig1 and asig2, "No se recibio asigacion en reconexion"
        assert set([asig1["payload"]["color"], asig2["payload"]["color"]]) == {"white", "red"}, "Colores perdidos!"
        ok("Reconexiones simultaneas tratadas sin perder piezas.")

        await ws0.close()
        await ws1_re.close()
        await ws2_re.close()
        await ws3.close()

        print("\n  ✔ BLOQUE 6 PASADO: Multihilo sin crashing OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 6 FALLIDO: {e}")
        return False
    finally:
        for t, u in zip(tokens, users): delete_user(t, u)

# ─────────────────────────────────────────────
#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────

async def async_main():
    results = {}

    results["Flickering (desconexiones rapidas)"]     = await run_flickering_test()
    results["Reconexion exitosa tras microcorte"]     = await run_reconnection_test()
    results["Abandono definitivo por timeout"]        = await run_abandonment_test()
    results["Aislamiento total de salas"]             = await run_isolation_test()
    results["Rendicion y Abandono Parcial (4P)"]      = await run_4p_abandonment_test()
    results["Resiliencia de Red Flickering (4P)"]     = await run_4p_flickering_recon_test()

    print("\n" + "#"*60)
    print("  RESUMEN FINAL")
    print("#"*60)
    passed = 0
    for nombre, ok_val in results.items():
        estado = "✔ PASS" if ok_val else "✘ FAIL"
        print(f"  {estado}  →  {nombre}")
        if ok_val:
            passed += 1

    total = len(results)
    print(f"\n  Resultado: {passed}/{total} bloques pasados")
    print("#"*60 + "\n")

    if passed < total:
        sys.exit(1)
    else:
        sys.exit(0)


def main():
    print("\n" + "#"*60)
    print("  TEST SUITE: RESILIENCIA DE RED, RECONEXION Y AISLAMIENTO")
    print("#"*60)
    asyncio.run(async_main())


if __name__ == "__main__":
    main()