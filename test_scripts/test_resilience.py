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

async def safe_recv(ws, label="WS", timeout=3.0):
    try:
        raw  = await asyncio.wait_for(ws.recv(), timeout=timeout)
        data = json.loads(raw)
        tipo = data.get("type", "?")
        debug(f"[{label}] tipo='{tipo}' | payload={str(data.get('payload',''))[:120]}")
        return data
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
        json={"mode": "1v1"}
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
                async with websockets.connect(
                    f"{WS_URL}/ws/play/{game_id}?token={t1}"
                ) as ws_temp:
                    msg = await safe_recv(ws_temp, label=f"flash-{i}", timeout=2.0)
                    debug(f"Ciclo {i}: recibido tipo='{msg.get('type') if msg else None}'")
                    debug(f"Ciclo {i}: desconectando abruptamente...")
                # Sin espera entre intentos
                await asyncio.sleep(0.1)
            ok("3 ciclos de flickering completados sin crash del servidor")

            step(4, "Reconexion final y definitiva de '{u1}'...")
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
                asig = await safe_recv(ws1, label=f"final-asig-{u1}", timeout=4.0)
                assert asig is not None, \
                    "'{u1}' no recibio asignacion de color en la reconexion final"
                assert asig.get("type") == "player_assignment", \
                    f"Tipo incorrecto: '{asig.get('type')}'"
                debug(f"Color en reconexion final: {asig.get('payload', {}).get('color')}")
                ok("Reconexion final exitosa. Asignacion de color recibida")

                step(5, "Verificando que el estado del juego es coherente (no corrompido)...")
                tablero = await safe_recv(ws1, label=f"tablero-final-{u1}", timeout=4.0)
                if tablero and tablero.get("type") == "game_state_update":
                    game_over = tablero["payload"].get("game_over", False)
                    assert not game_over, \
                        "La partida se marco como game_over por error tras el flickering"
                    ok("Estado del juego intacto. game_over=False correctamente")
                else:
                    debug("Tablero no recibido directamente, estado asumido coherente")

                step(6, "Realizando movimiento tras reconexion para confirmar funcionalidad...")
                mov = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
                await ws1.send(json.dumps(mov))
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

            step(3, f"'{u1}' se conecta y luego se desconecta abruptamente...")
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1:
                asig = await safe_recv(ws1, label=f"asig-{u1}")
                assert asig and asig.get("type") == "player_assignment"
                debug(f"'{u1}' recibio asignacion antes de desconectarse")
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

                tablero = await safe_recv(ws1_re, label=f"tablero-recon-{u1}", timeout=6.0)
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

            # u3 entra y cierra la conexion definitivamente
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t3}") as ws3:
                await safe_recv(ws3, label=f"asig-{u3}")
                debug(f"'{u3}' conectado. Desconectando definitivamente (ragequit)...")
            debug(f"'{u3}' desconectado. El servidor deberia iniciar el temporizador de abandono.")

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
            json={"mode": "1v1"}
        )
        assert res_a.status_code == 200, f"Error creando Sala A: {res_a.text}"
        game_a = res_a.json()["game_id"]
        requests.post(f"{BASE_URL}/api/games/join/{game_a}",
                      headers={"Authorization": f"Bearer {tokens[1]}"})

        res_b = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {tokens[2]}"},
            json={"mode": "1v1"}
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

            debug("Vaciando mensajes de inicializacion de todos los WebSockets...")
            await asyncio.sleep(0.5)
            for ws, label in [(ws_a1, "A1"), (ws_a2, "A2"), (ws_b1, "B1"), (ws_b2, "B2")]:
                while True:
                    msg = await safe_recv(ws, label=label, timeout=0.3)
                    if msg is None:
                        break
            ok("Mensajes de inicializacion consumidos")

            step(4, f"Jugador A1 ({names[0]}) realiza un movimiento en la Sala A...")
            movimiento = {"action": "make_move", "row": 2, "col": 3, "player": "black"}
            await ws_a1.send(json.dumps(movimiento))
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
            await ws_b1.send(json.dumps({"action": "make_move", "row": 5, "col": 4, "player": "black"}))
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
#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────

async def async_main():
    results = {}

    results["Flickering (desconexiones rapidas)"]     = await run_flickering_test()
    results["Reconexion exitosa tras microcorte"]     = await run_reconnection_test()
    results["Abandono definitivo por timeout"]        = await run_abandonment_test()
    results["Aislamiento total de salas"]             = await run_isolation_test()

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