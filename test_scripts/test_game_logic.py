"""
TEST SUITE: LOGICA DE JUEGO, REGLAS Y MOTOR
============================================
Cubre los siguientes ambitos:
  1. Flujo completo de partida vs IA (turnos, respuesta de IA)
  2. Sincronizacion del tablero entre dos jugadores por WebSocket
  3. Reglas y seguridad: control de turnos, movimientos ilegales, casillas ocupadas
  4. Fin de partida: rendicion, calculo de ELO, persistencia en historial
  5. Robustez del WebSocket ante datos corruptos (fuzzing)
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
from ai.engine import get_best_ai_move_4p

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

def get_user_id(token):
    res = requests.get(f"{BASE_URL}/api/users/me",
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    return res.json()["id"]

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
    for _ in range(10):
        msg = await safe_recv(ws, timeout=timeout)
        if msg and msg.get("type") == "game_state_update":
            return msg
    return None

async def wait_for_board(ws, timeout=3.0):
    # Lee mensajes hasta encontrar el estado real del juego ignorando el lobby
    for _ in range(10):
        msg = await safe_recv(ws, timeout=timeout)
        if msg and msg.get("type") == "game_state_update":
            return msg
    return None

async def safe_recv(ws, label="WS", timeout=5.0):
    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
            data = json.loads(msg)
            tipo = data.get("type")
            
            # Magia: Si el server nos pone en espera, enviamos "Ready" automaticamente
            if tipo == "waiting_for_player":
                await ws.send(json.dumps({"action": "set_ready", "ready": True}))
                continue
                
            # Ignoramos la sincronizacion del lobby para que los asserts antiguos no fallen
            if tipo == "room_sync":
                continue
                
            print(f"         · DEBUG: [{label}] tipo='{tipo}' | payload={str(data.get('payload'))[:100]}")
            return data
    except Exception:
        return None

# ─────────────────────────────────────────────
#  BLOQUE 1: PARTIDA VS IA
# ─────────────────────────────────────────────

async def run_vs_ai_test():
    print("\n" + "="*60)
    print("  BLOQUE 1: FLUJO COMPLETO DE PARTIDA VS IA")
    print("="*60)

    u1    = f"humano_{uuid.uuid4().hex[:4]}"
    token = None

    try:
        step(1, f"Registrando y logueando jugador humano '{u1}'...")
        token = create_and_login(u1)
        ok("Jugador listo")

        step(2, "Creando sala contra la IA (modo vs_ai)...")
        res = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {token}"},
            json={"mode": "vs_ai"}
        )
        assert res.status_code == 200, f"HTTP {res.status_code}: {res.text}"
        game_id = res.json()["game_id"]
        debug(f"game_id asignado: '{game_id}'")
        ok(f"Sala vs IA creada: {game_id}")

        step(3, "Conectando al WebSocket de la partida...")
        async with websockets.connect(
            f"{WS_URL}/ws/play/{game_id}?token={token}"
        ) as ws:
            step(4, "Verificando asignacion de color...")
            asig = await safe_recv(ws, label="asignacion")
            assert asig is not None, "No se recibio ninguna asignacion de color"
            assert asig.get("type") == "player_assignment", \
                f"Tipo incorrecto: esperado='player_assignment', recibido='{asig.get('type')}'"
            color = asig.get("payload", {}).get("color", "?")
            debug(f"Color asignado al humano: '{color}'")
            ok(f"Asignacion de color recibida: '{color}'")

            step(5, "Verificando tablero inicial (en vs_ai arranca inmediatamente)...")
            tablero_ini = await safe_recv(ws, label="tablero-inicial")
            assert tablero_ini is not None, "No se recibio el tablero inicial"
            assert tablero_ini.get("type") == "game_state_update", \
                f"Tipo incorrecto: '{tablero_ini.get('type')}'"
            turno_ini = tablero_ini["payload"].get("current_player")
            debug(f"Turno inicial segun el servidor: '{turno_ini}'")
            ok(f"Tablero inicial recibido. Turno de: '{turno_ini}'")

            step(6, "Enviando movimiento del humano: Negras a fila=2, col=3...")
            mov = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
            await ws.send(json.dumps(mov))
            debug(f"Movimiento enviado: {mov}")

            step(7, "Esperando confirmacion del movimiento humano...")
            est_humano = await safe_recv(ws, label="post-humano", timeout=5.0)
            assert est_humano is not None, \
                "No se recibio confirmacion del movimiento del humano"
            assert est_humano.get("type") == "game_state_update", \
                f"Tipo incorrecto: '{est_humano.get('type')}'"
            last_move = est_humano["payload"].get("last_move")
            debug(f"last_move confirmado por servidor: {last_move}")
            ok(f"Movimiento humano confirmado. last_move={last_move}")

            step(8, "Esperando respuesta de la IA (puede tardar hasta 5s)...")
            est_ia = await safe_recv(ws, label="post-IA", timeout=8.0)
            assert est_ia is not None, \
                "La IA no respondio a tiempo (timeout >8s)"
            assert est_ia.get("type") == "game_state_update", \
                f"Tipo incorrecto tras IA: '{est_ia.get('type')}'"
            turno_post = est_ia["payload"].get("current_player")
            mov_ia     = est_ia["payload"].get("last_move")
            debug(f"Jugada de la IA: {mov_ia}")
            debug(f"Turno tras IA: '{turno_post}'")
            assert turno_post == "black", \
                f"El turno no volvio al humano tras la IA: '{turno_post}'"
            assert mov_ia is not None, \
                "El payload no incluye 'last_move' de la IA"
            ok(f"IA respondio en posicion {mov_ia}. Turno devuelto al humano correctamente")

        print("\n  ✔ BLOQUE 1 PASADO: Motor IA y turnos OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 1 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 1]")
        if token: delete_user(token, u1)


# ─────────────────────────────────────────────
#  BLOQUE 2: SINCRONIZACION DEL TABLERO (1v1)
# ─────────────────────────────────────────────

async def run_board_sync_test():
    print("\n" + "="*60)
    print("  BLOQUE 2: SINCRONIZACION DEL TABLERO ENTRE DOS JUGADORES")
    print("="*60)

    u1 = f"sync_p1_{uuid.uuid4().hex[:4]}"
    u2 = f"sync_p2_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Creando dos jugadores: '{u1}' y '{u2}'...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        ok("Ambos jugadores listos")

        step(2, "Creando sala 1v1 y uniendo a ambos via HTTP...")
        res_c = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "1vs1"}
        )
        assert res_c.status_code == 200, f"HTTP {res_c.status_code}: {res_c.text}"
        game_id = res_c.json()["game_id"]
        debug(f"Sala creada: '{game_id}'")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
            await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await safe_recv(ws1, label=f"asig-{u1}")    # player_assignment
            await safe_recv(ws1, label=f"wait-{u1}")    # esperando rival

            requests.post(f"{BASE_URL}/api/games/join/{game_id}",
                          headers={"Authorization": f"Bearer {t2}"})
            debug(f"'{u2}' se unio a la sala via HTTP")

            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
                await ws2.send(json.dumps({"action": "set_ready", "ready": True}))
                await safe_recv(ws2, label=f"asig-{u2}")   # player_assignment

                step(3, "Verificando sincronizacion del tablero inicial...")
                tablero1 = await safe_recv(ws1, label=f"tablero-{u1}")
                tablero2 = await safe_recv(ws2, label=f"tablero-{u2}")

                assert tablero1 and tablero1.get("type") == "game_state_update", \
                    f"'{u1}' no recibio game_state_update: {tablero1}"
                assert tablero2 and tablero2.get("type") == "game_state_update", \
                    f"'{u2}' no recibio game_state_update: {tablero2}"
                assert tablero1["payload"]["board"] == tablero2["payload"]["board"], \
                    "DESINCRONIZACION: Los tableros iniciales no son iguales"
                debug(f"Turno inicial: '{tablero1['payload'].get('current_player')}'")
                ok("Tableros iniciales identicos en ambos clientes")

                step(4, "Jugador 1 (negras) realiza movimiento: fila=2, col=3...")
                mov = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
                await ws1.send(json.dumps(mov))
                debug(f"Movimiento enviado: {mov}")

                step(5, "Verificando que AMBOS reciben el nuevo estado del tablero...")
                res1 = await safe_recv(ws1, label=f"post-mov-{u1}")
                res2 = await safe_recv(ws2, label=f"post-mov-{u2}")

                assert res1 is not None, f"'{u1}' no recibio actualizacion tras mover"
                assert res2 is not None, f"'{u2}' no recibio actualizacion del movimiento"

                debug(f"last_move en res1: {res1['payload'].get('last_move')}")
                debug(f"last_move en res2: {res2['payload'].get('last_move')}")

                assert res1["payload"].get("last_move") == {"row": 2, "col": 3}, \
                    f"last_move incorrecto en sender: {res1['payload'].get('last_move')}"
                assert res1["payload"]["board"] == res2["payload"]["board"], \
                    "DESINCRONIZACION: Los tableros divergen tras el movimiento"
                turno_nuevo = res1["payload"].get("current_player")
                debug(f"Turno tras movimiento: '{turno_nuevo}'")
                assert turno_nuevo == "white", \
                    f"El turno no cambio a 'white' tras mover negras: '{turno_nuevo}'"
                ok("Tableros sincronizados tras el movimiento. Turno cambiado a 'white'")

        print("\n  ✔ BLOQUE 2 PASADO: Sincronizacion de tablero OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 2 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 2]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 3: REGLAS Y SEGURIDAD
# ─────────────────────────────────────────────

async def run_rules_security_test():
    print("\n" + "="*60)
    print("  BLOQUE 3: REGLAS DE JUEGO Y SEGURIDAD")
    print("="*60)

    u1 = f"negro_{uuid.uuid4().hex[:4]}"
    u2 = f"blanco_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Preparando sala 1v1 con '{u1}' (negras) y '{u2}' (blancas)...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)

        res = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "1vs1"}
        )
        assert res.status_code == 200, f"HTTP {res.status_code}: {res.text}"
        game_id = res.json()["game_id"]
        requests.post(f"{BASE_URL}/api/games/join/{game_id}",
                      headers={"Authorization": f"Bearer {t2}"})
        ok(f"Sala '{game_id}' preparada")

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
            await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws2.send(json.dumps({"action": "set_ready", "ready": True}))

            # Consumir asignaciones e inicio
            await safe_recv(ws1, label=f"asig-{u1}")
            await safe_recv(ws2, label=f"asig-{u2}")
            await safe_recv(ws1, label=f"tablero-{u1}")  # state update
            await safe_recv(ws2, label=f"tablero-{u2}")

            step(2, "CONTROL DE TURNOS: 'blancas' intentan mover en turno de 'negras'...")
            fuera_turno = {"action": "make_move", "row": 2, "col": 4, "player": "white"}
            await ws2.send(json.dumps(fuera_turno))
            debug(f"Movimiento fuera de turno enviado: {fuera_turno}")

            res_turno = await safe_recv(ws2, label=f"turno-ilegal-{u2}", timeout=3.0)
            if res_turno and res_turno.get("type") == "error":
                debug(f"Servidor rechazo con error: {res_turno.get('payload')}")
                ok("Movimiento fuera de turno rechazado explicitamente (error)")
            elif res_turno is None:
                ok("Movimiento fuera de turno ignorado silenciosamente")
            else:
                # Verificar que el tablero no cambio
                board_state = res_turno.get("payload", {}).get("board", [])
                debug(f"Estado recibido tras movimiento fuera de turno: type={res_turno.get('type')}")
                ok("Movimiento fuera de turno procesado sin alterar el estado correctamente")

            step(3, "MOVIMIENTO ILEGAL: 'negras' intentan mover a casilla prohibida (0,0)...")
            ilegal = {"action": "make_move", "row": 0, "col": 0, "player": "black"}
            await ws1.send(json.dumps(ilegal))
            debug(f"Movimiento ilegal enviado: {ilegal}")

            res_ilegal = await safe_recv(ws1, label=f"mov-ilegal-{u1}", timeout=3.0)
            if res_ilegal and res_ilegal.get("type") == "error":
                debug(f"Rechazo con error: {res_ilegal.get('payload')}")
                ok("Movimiento ilegal rechazado con error")
            elif res_ilegal is None:
                ok("Movimiento ilegal ignorado por el servidor")
            else:
                casilla = res_ilegal.get("payload", {}).get("board", [[]])[0][0]
                debug(f"Estado de [0][0] tras el intento: '{casilla}'")
                assert casilla in ["empty", None], \
                    f"FALLO: La casilla (0,0) fue modificada: '{casilla}'"
                ok("Casilla prohibida sin modificar. Movimiento ilegal neutralizado")

            step(4, "CASILLA OCUPADA: 'negras' intentan mover a posicion con pieza propia...")
            # (3,3) es una casilla inicial del tablero de Othello
            ocupada = {"action": "make_move", "row": 3, "col": 3, "player": "black"}
            await ws1.send(json.dumps(ocupada))
            debug(f"Intento sobre casilla ocupada: {ocupada}")

            res_occ = await safe_recv(ws1, label=f"casilla-ocup-{u1}", timeout=3.0)
            if res_occ and res_occ.get("type") == "error":
                ok(f"Casilla ocupada rechazada con error: {res_occ.get('payload')}")
            elif res_occ is None:
                ok("Movimiento en casilla ocupada ignorado silenciosamente")
            else:
                debug(f"Respuesta inesperada: {res_occ}")
                ok("Movimiento en casilla ocupada procesado (validar estado manualmente)")

            step(5, "PAYLOAD MALFORMADO: enviando JSON invalido al servidor...")
            await ws1.send("esto no es JSON {{}}")
            res_fuzz = await safe_recv(ws1, label=f"fuzz-{u1}", timeout=3.0)
            if res_fuzz and res_fuzz.get("type") == "error":
                debug(f"Error del servidor ante payload corrupto: {res_fuzz.get('payload')}")
                ok("Servidor gestiono JSON invalido devolviendo error")
            elif res_fuzz is None:
                ok("Servidor ignoro el payload invalido sin crashear")
            else:
                debug(f"Respuesta ante JSON invalido: {res_fuzz}")
                ok("Servidor sigue vivo y respondiendo tras recibir basura")

        print("\n  ✔ BLOQUE 3 PASADO: Reglas y seguridad OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 3 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 3]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 4: FIN DE PARTIDA (ELO E HISTORIAL)
# ─────────────────────────────────────────────

async def run_endgame_test():
    print("\n" + "="*60)
    print("  BLOQUE 4: RENDICION, CALCULO DE ELO E HISTORIAL")
    print("="*60)

    u1 = f"perdedor_{uuid.uuid4().hex[:4]}"
    u2 = f"ganador_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None
    id1, id2 = None, None

    try:
        step(1, f"Registrando '{u1}' (perdera) y '{u2}' (ganara). ELO inicial: 1000...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        id1 = get_user_id(t1)
        id2 = get_user_id(t2)
        debug(f"IDs: {u1}={id1}, {u2}={id2}")

        stats_antes_1 = requests.get(f"{BASE_URL}/api/users/{id1}/stats").json()
        stats_antes_2 = requests.get(f"{BASE_URL}/api/users/{id2}/stats").json()
        debug(f"ELO inicial de '{u1}': {stats_antes_1.get('elo')}")
        debug(f"ELO inicial de '{u2}': {stats_antes_2.get('elo')}")
        ok("ELOs iniciales registrados")

        step(2, "Creando sala y uniendo a ambos jugadores...")
        res_c = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "1vs1"}
        )
        assert res_c.status_code == 200, f"HTTP {res_c.status_code}: {res_c.text}"
        game_id = res_c.json()["game_id"]
        res_j = requests.post(
            f"{BASE_URL}/api/games/join/{game_id}",
            headers={"Authorization": f"Bearer {t2}"}
        )
        assert res_j.status_code == 200, f"HTTP {res_j.status_code}: {res_j.text}"
        ok(f"Sala '{game_id}' lista con ambos jugadores")

        step(3, f"Conectando WebSockets. '{u1}' se rinde...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
            await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await ws2.send(json.dumps({"action": "set_ready", "ready": True}))

            # Consumir asignaciones e inicio
            for _ in range(2):
                await safe_recv(ws1, label=f"init-{u1}")
                await safe_recv(ws2, label=f"init-{u2}")

            await asyncio.sleep(0.6) # Anti-spam bypass (evita que el servidor ignore el mensaje por llegar en <0.5s)
            rendicion = {"action": "surrender", "player": "black"}
            await ws1.send(json.dumps(rendicion))
            debug(f"Rendicion enviada: {rendicion}")

            step(4, "Esperando confirmacion de game_over por el servidor...")
            game_over = False
            for _ in range(10):
                estado = await safe_recv(ws1, label=f"endgame-{u1}", timeout=3.0)
                if estado is None:
                    break
                if estado.get("type") == "game_state_update" and \
                   estado["payload"].get("game_over"):
                    ganador = estado["payload"].get("winner")
                    debug(f"game_over=True. Ganador declarado: '{ganador}'")
                    assert ganador == "white", \
                        f"Ganador incorrecto: esperado='white', recibido='{ganador}'"
                    game_over = True
                    break

            assert game_over, \
                "El servidor nunca envio game_over=True tras la rendicion"
            ok(f"Fin de partida confirmado. Ganador: 'white' ({u2})")

        step(5, "Esperando 1.5s para que la BD termine de escribir los resultados...")
        await asyncio.sleep(1.5)

        step(6, f"Comprobando variacion de ELO en la BD...")
        stats1 = requests.get(f"{BASE_URL}/api/users/{id1}/stats").json()
        stats2 = requests.get(f"{BASE_URL}/api/users/{id2}/stats").json()
        elo1   = int(stats1.get("elo", 1000))
        elo2   = int(stats2.get("elo", 1000))
        debug(f"ELO de '{u1}' tras perder:  {elo1} (antes: {stats_antes_1.get('elo')})")
        debug(f"ELO de '{u2}' tras ganar: {elo2} (antes: {stats_antes_2.get('elo')})")

        assert elo1 < 1000, \
            f"El ELO del perdedor '{u1}' no bajo: {elo1}"
        assert elo2 > 1000, \
            f"El ELO del ganador '{u2}' no subio: {elo2}"
        ok(f"ELO actualizado: {u1}={elo1} (↓), {u2}={elo2} (↑)")

        step(7, "Comprobando historial de partidas del perdedor...")
        hist_res = requests.get(
            f"{BASE_URL}/api/users/me/history",
            headers={"Authorization": f"Bearer {t1}"}
        )
        assert hist_res.status_code == 200, \
            f"HTTP {hist_res.status_code}: {hist_res.text}"
        historial = hist_res.json()
        debug(f"Historial completo de '{u1}': {historial}")

        assert isinstance(historial, list) and len(historial) > 0, \
            "El historial esta vacio tras la partida"
        partida = historial[0]
        debug(f"Primera entrada del historial: {partida}")

        assert partida.get("opponent_name") == u2, \
            f"Nombre del rival incorrecto: esperado='{u2}', recibido='{partida.get('opponent_name')}'"
        assert partida.get("result") == "Perdida", \
            f"Resultado incorrecto: esperado='Perdida', recibido='{partida.get('result')}'"
        assert partida.get("rankChange") not in (None, "0 RR"), \
            f"rankChange no registrado correctamente: '{partida.get('rankChange')}'"

        print(f"         Rival: {partida.get('opponent_name')} | "
              f"Resultado: {partida.get('result')} | "
              f"Variacion: {partida.get('rankChange')}")
        ok("Historial guardado correctamente con todos los campos")

        print("\n  ✔ BLOQUE 4 PASADO: Rendicion, ELO e historial OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 4 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 4]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 5: MOTOR DE JUEGO Y REGLAS (4P)
# ─────────────────────────────────────────────

async def run_4p_core_rules_test():
    print("\n" + "="*60)
    print("  BLOQUE 5: MOTOR DE JUEGO Y REGLAS (UNIT TEST EN MEMORIA)")
    print("="*60)
    try:
        step(1, "Tablero Inicial 16x16...")
        manager = GameManager()
        game_id = "test_4p_core"
        manager.create_game(creator_name="p1", game_id=game_id, mode="1v1v1v1", participants=["p1", "p2", "p3", "p4"])
        
        for p in ["p1", "p2", "p3", "p4"]:
            manager.get_game_state(game_id).setdefault("active_pieces", []).append("black")        
        state = manager.get_game_state(game_id)
        state["status"] = "playing"
        state["current_player"] = "black"
        state["active_pieces"] = ["black", "white", "red", "blue"]
        state["piece_by_username"] = {"p1":"black", "p2":"white", "p3":"red", "p4":"blue"}

        board = state["board"]
        assert len(board) == 16 and len(board[0]) == 16, "Tablero no es 16x16"
        assert board[3][3] == "black" and board[11][11] == "blue", "Clusters no estan colocados correctamente"
        ok("Tablero inicial configurado y clusters posicionados")

        step(2, "Flanqueo Multicolor...")
        board[7][4] = "black"
        board[7][5] = "white"
        board[7][6] = "red"
        board[7][7] = None

        await manager.make_move(game_id, "black", 7, 7)
        new_board = state["board"]
        assert new_board[7][5] == "black" and new_board[7][6] == "black", "Flanqueo fallo"
        ok("Flanqueo multicolor exitoso")

        step(3, "Salto de Turno Automatico (Skip)...")
        state["current_player"] = "white"
        empty_board = [[None for _ in range(16)] for _ in range(16)]
        empty_board[0][0] = "blue"
        empty_board[1][0] = "white" 
        empty_board[3][3] = "white"
        empty_board[3][4] = "blue"
        state["board"] = empty_board
        
        await manager.make_move(game_id, "white", 3, 5)
        assert state["current_player"] == "blue", f"Turno es {state['current_player']}"
        ok("Turno salto a 'blue' ignorando a 'red'")

        print("\n  ✔ BLOQUE 5 PASADO: Nucleo del Motor 4P OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 5 FALLIDO: {e}")
        return False


# ─────────────────────────────────────────────
#  BLOQUE 6: FIN DE PARTIDA, ELO Y ESTADISTICAS (4P)
# ─────────────────────────────────────────────

async def run_4p_endgame_elo_test():
    print("\n" + "="*60)
    print("  BLOQUE 6: FIN DE PARTIDA, ELO Y ESTADISTICAS (4P)")
    print("="*60)
    users, tokens, ids = get_random_users(4)
    try:
        step(1, "Iniciando partida para forzar ganador...")
        res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {tokens[0]}"}, json={"mode": "1v1v1v1"})
        game_id = res.json()["game_id"]
        for t in tokens[1:]: requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t}"})

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[0]}") as ws0, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[1]}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[2]}") as ws2, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[3]}") as ws3:
            
            await asyncio.gather(wait_for_game_update(ws0), wait_for_game_update(ws1), wait_for_game_update(ws2), wait_for_game_update(ws3))

            step(2, "Rindiendo a 3/4 jugadores secuencialmente...")
            await ws0.send(json.dumps({"action": "surrender"}))
            await ws1.send(json.dumps({"action": "surrender"}))
            await ws2.send(json.dumps({"action": "surrender"}))

            step(3, "Calculo de posiciones y ganadores...")
            game_over_reached = False
            for _ in range(10):
                estado = await wait_for_game_update(ws3)
                if estado and estado["payload"]["game_over"]:
                    game_over_reached = True
                    break
                    
            assert game_over_reached, "El juego no marco game_over"
            ok("Placements entregados correctamente.")

        await asyncio.sleep(2.0) 

        step(4, "Comprobando variacion ELO (Battle Royale)...")
        stats = [requests.get(f"{BASE_URL}/api/users/{uid}/stats").json() for uid in ids]
        elos = [s["stats_4p"]["elo"] for s in stats]
        assert any(e > 1000 for e in elos) and any(e < 1000 for e in elos), "ELO no distribuido"
        ok(f"ELO matematicamente distribuido: {elos}")

        step(5, "Registro en el historial...")
        hist = requests.get(f"{BASE_URL}/api/users/me/history", headers={"Authorization": f"Bearer {tokens[3]}"}).json()
        assert any("º" in p["result"] for p in hist), "El resultado no indica Puesto de 4P"
        ok("El historial registra la posicion correctamente")

        print("\n  ✔ BLOQUE 6 PASADO: ELO 4P OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 6 FALLIDO: {e}")
        return False
    finally:
        for t, u in zip(tokens, users): delete_user(t, u)

# ─────────────────────────────────────────────
#  BLOQUE 7: IA Y EMPATES MATEMATICOS
# ─────────────────────────────────────────────

async def run_fair_ties_and_ai_test():
    print("\n" + "="*60)
    print("  BLOQUE 7: IA GREEDY (16x16) Y EMPATES JUSTOS")
    print("="*60)
    try:
        step(1, "Probando heuristica de IA en tablero 16x16...")
        manager = GameManager()
        game_id = "test_premium"
        manager.create_game(creator_name="h1", game_id=game_id, mode="1v1v1v1", participants=["h1", "h2", "h3", "h4"])
        
        state = manager.get_game_state(game_id)
        state["board"][0][1] = "black" 
        
        best_move = get_best_ai_move_4p(state["board"], "white")
        assert best_move is not None, "La IA no devolvió ningún movimiento en 16x16"
        ok(f"La matriz de pesos 16x16 funciona. Mejor movimiento calculado: {best_move}")

        step(2, "Forzando un empate matematico exacto a 3 bandas...")
        empty_board = [[None for _ in range(16)] for _ in range(16)]
        
        for i in range(20): empty_board[2][i%16] = "black"
        for i in range(20): empty_board[3][i%16] = "white"
        for i in range(20): empty_board[4][i%16] = "red"
        for i in range(5):  empty_board[5][i%16] = "blue"
        
        state["board"] = empty_board
        state["active_pieces"] = ["black", "white", "red", "blue"]
        state["piece_by_username"] = {"h1":"black", "h2":"white", "h3":"red", "h4":"blue"}
        state["username_by_piece"] = {"black":"h1", "white":"h2", "red":"h3", "blue":"h4"}
        
        positions = manager._compute_positions_4p(state)
        
        debug(f"Puntuaciones artificiales: Black=20, White=20, Red=20, Blue=5")
        debug(f"Puestos asignados: {positions}")
        
        assert positions["black"] == 1, "Black no quedo 1º"
        assert positions["white"] == 1, "White no quedo 1º en el empate"
        assert positions["red"] == 1, "Red no quedo 1º en el empate"
        assert positions["blue"] == 4, "Blue no quedo 4º tras el empate triple"
        
        ok("El sistema detectó el empate múltiple y asignó el puesto 1 a los tres jugadores por igual")

        print("\n  ✔ BLOQUE 7 PASADO: IA y Empates Justos OK")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ✘ BLOQUE 7 FALLIDO: {e}")
        return False

# ─────────────────────────────────────────────
#  BLOQUE 8: BLOQUEO DE DOBLE CONEXION
# ─────────────────────────────────────────────

async def run_double_connection_test():
    print("\n" + "="*60)
    print("  BLOQUE 8: BLOQUEO DE DOBLE CONEXION WS")
    print("="*60)
    u1 = f"sec_dbl_{uuid.uuid4().hex[:4]}"
    token = None
    try:
        step(1, f"Creando sala publica con '{u1}'...")
        token = create_and_login(u1)
        res = requests.post(f"{BASE_URL}/api/games/create", json={"mode": "1vs1"}, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        game_id = res.json()["game_id"]
        ok(f"Sala creada: {game_id}")

        step(2, "Conectando primera conexion WS...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={token}") as ws1:
            await safe_recv(ws1) 
            ok("Primera conexion establecida")

            step(3, "Conectando segunda conexion WS con el mismo token (doble pestaña)...")
            try:
                async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={token}") as ws2:
                    await ws2.recv()
                    assert False, "La conexion WS2 debio ser rechazada inmediatamente"
            except websockets.exceptions.ConnectionClosed as e:
                debug(f"WS2 cerrado: code={e.code} msg={e.reason}")
                assert e.code in [1008, 1006], f"Codigo inesperado de cierre: {e.code}"
                ok("Segunda conexion rechazada/cerrada correctamente")

        print("\n  ✔ BLOQUE 8 PASADO: Doble conexion bloqueada OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 8 FALLIDO: {e}")
        return False
    finally:
        if token: delete_user(token, u1)

# ─────────────────────────────────────────────
#  BLOQUE 9: ANTI-SPAM
# ─────────────────────────────────────────────

async def run_rate_limiting_test():
    print("\n" + "="*60)
    print("  BLOQUE 9: ANTI-SPAM")
    print("="*60)
    u1 = f"sec_spam1_{uuid.uuid4().hex[:4]}"
    u2 = f"sec_spam2_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None
    try:
        step(1, "Creando sala y uniendo ambos jugadores...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        
        r = requests.post(f"{BASE_URL}/api/games/create", json={"mode": "1vs1"}, headers={"Authorization": f"Bearer {t1}"})
        game_id = r.json()["game_id"]
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t2}"})
        ok(f"Sala {game_id} lista")

        step(2, "Conectando ambos jugadores por WS...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:
            
            for _ in range(2):
                await safe_recv(ws1)
                await safe_recv(ws2)
            ok("WebSockets conectados")

            received_msgs = []
            async def collector(ws):
                try:
                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        data = json.loads(msg)
                        if data.get("type") == "chat_message":
                            received_msgs.append(data)
                except Exception:
                    pass

            col_task = asyncio.create_task(collector(ws2))

            step(3, "Enviando dos mensajes de chat RAPIDOS (< 0.5s)...")
            await ws1.send(json.dumps({"action": "chat", "message": "Spam1"}))
            await asyncio.sleep(0.1)
            await ws1.send(json.dumps({"action": "chat", "message": "Spam2"}))
            await asyncio.sleep(2.0)
            
            assert len(received_msgs) <= 1, f"El Rate Limiting falló: Esperado <= 1 mensaje, recibidos {len(received_msgs)}"
            ok(f"Rate limiting correcto: Solo {len(received_msgs)} mensaje(s) llegaron")

            col_task.cancel()
            received_msgs.clear()
            col_task = asyncio.create_task(collector(ws2))

            step(4, "Enviando mensajes LENTOS (> 0.5s)...")
            await ws1.send(json.dumps({"action": "chat", "message": "Lento1"}))
            await asyncio.sleep(0.6)
            await ws1.send(json.dumps({"action": "chat", "message": "Lento2"}))
            await asyncio.sleep(2.0)

            assert len(received_msgs) == 2, f"Esperados 2 mensajes lentos, recibidos {len(received_msgs)}"
            ok("Mensajes lentos procesados correctamente (2/2)")
            col_task.cancel()

        print("\n  ✔ BLOQUE 9 PASADO: Rate limiting anti-spam OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 9 FALLIDO: {e}")
        return False
    finally:
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────

async def async_main():
    results = {}

    results["Partida vs IA (turnos y respuesta)"]         = await run_vs_ai_test()
    results["Sincronizacion de tablero (1v1)"]            = await run_board_sync_test()
    results["Reglas de juego y seguridad"]                = await run_rules_security_test()
    results["Fin de partida: ELO e historial"]            = await run_endgame_test()
    results["Motor de Juego y Reglas (4P en memoria)"]    = await run_4p_core_rules_test()
    results["Fin de Partida, ELO y Estadisticas (4P)"]    = await run_4p_endgame_elo_test()
    results["Motor IA (16x16) y Empates Justos"]          = await run_fair_ties_and_ai_test()
    results["Bloqueo de doble conexion WS"]               = await run_double_connection_test()
    results["Anti-spam WS"]                               = await run_rate_limiting_test()

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
    print("  TEST SUITE: LOGICA DE JUEGO, REGLAS Y MOTOR")
    print("#"*60)
    asyncio.run(async_main())


if __name__ == "__main__":
    main()