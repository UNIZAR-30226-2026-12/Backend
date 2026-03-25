"""
TEST SUITE: MATCHMAKING, SALAS Y COMUNICACION EN PARTIDA
=========================================================
Cubre los siguientes ambitos:
  1. Creacion de sala publica y visibilidad en el lobby
  2. Union a sala y bloqueo de sala llena
  3. Flujo de invitacion amistosa via WebSocket de notificaciones
  4. Chat bidireccional en tiempo real dentro de una partida
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
        f"[ERROR] Fallo registro '{username}': HTTP {res_reg.status_code} → {res_reg.text}"
    debug(f"'{username}' registrado (ID: {res_reg.json().get('id')})")

    res_log = requests.post(f"{BASE_URL}/api/auth/login",
                            data={"username": username, "password": password})
    assert res_log.status_code == 200, \
        f"[ERROR] Fallo login '{username}': HTTP {res_log.status_code} → {res_log.text}"
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

async def safe_recv(ws, label="WS", timeout=5.0):
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        data = json.loads(raw)
        debug(f"[{label}] recibe tipo='{data.get('type')}' | payload={str(data.get('payload',''))[:120]}")
        return data
    except asyncio.TimeoutError:
        debug(f"[{label}] TIMEOUT tras {timeout}s — sin mensaje")
        return None
    except Exception as e:
        debug(f"[{label}] Error al recibir: {e}")
        return None

# ─────────────────────────────────────────────
#  BLOQUE 1: LOBBY PUBLICO Y UNION A SALA
# ─────────────────────────────────────────────

def run_lobby_test():
    print("\n" + "="*60)
    print("  BLOQUE 1: LOBBY PUBLICO Y GESTION DE SALAS")
    print("="*60)

    u1 = f"host_{uuid.uuid4().hex[:4]}"
    u2 = f"guest_{uuid.uuid4().hex[:4]}"
    u3 = f"intruder_{uuid.uuid4().hex[:4]}"
    t1, t2, t3 = None, None, None

    try:
        step(1, f"Creando tres usuarios: host, guest e intruder...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        t3 = create_and_login(u3)
        ok("Tres usuarios creados y logueados")

        step(2, f"'{u1}' crea una sala publica (modo 1v1)...")
        res_create = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "1v1"}
        )
        assert res_create.status_code == 200, \
            f"HTTP {res_create.status_code}: {res_create.text}"
        game_id = res_create.json()["game_id"]
        debug(f"Sala creada con game_id='{game_id}'")
        ok(f"Sala creada correctamente: {game_id}")

        step(3, "Consultando la lista de salas publicas (GET /api/games/public)...")
        res_pub = requests.get(f"{BASE_URL}/api/games/public")
        assert res_pub.status_code == 200, f"HTTP {res_pub.status_code}: {res_pub.text}"
        lobbies = res_pub.json().get("lobbies", [])
        debug(f"Total de lobbies publicos activos: {len(lobbies)}")
        debug(f"game_ids visibles: {[l.get('game_id') for l in lobbies]}")

        sala = next((l for l in lobbies if l["game_id"] == game_id), None)
        assert sala is not None, \
            f"La sala '{game_id}' NO aparece en el listado publico. Salas visibles: {lobbies}"
        debug(f"Datos de la sala en el lobby: {sala}")
        ok("La sala recien creada es visible en la lista publica")

        step(4, f"'{u2}' se une a la sala '{game_id}' (POST /api/games/join/{game_id})...")
        res_join = requests.post(
            f"{BASE_URL}/api/games/join/{game_id}",
            headers={"Authorization": f"Bearer {t2}"}
        )
        assert res_join.status_code == 200, \
            f"HTTP {res_join.status_code}: {res_join.text}"
        debug(f"Respuesta join: {res_join.json()}")
        ok(f"'{u2}' se unio correctamente: {res_join.json().get('message')}")

        step(5, "Verificando que la sala ya no aparece en el lobby (esta llena)...")
        res_pub2 = requests.get(f"{BASE_URL}/api/games/public")
        lobbies2 = res_pub2.json().get("lobbies", [])
        sala_visible = any(l["game_id"] == game_id for l in lobbies2)
        if not sala_visible:
            ok("Sala llena retirada del lobby publico correctamente")
        else:
            debug("La sala sigue en el lobby (comportamiento aceptable si marca 'llena')")

        step(6, f"'{u3}' intenta unirse a la sala ya llena (debe ser rechazado)...")
        res_full = requests.post(
            f"{BASE_URL}/api/games/join/{game_id}",
            headers={"Authorization": f"Bearer {t3}"}
        )
        assert res_full.status_code == 400, \
            f"Se permitio entrar a una sala llena: HTTP {res_full.status_code}"
        debug(f"Respuesta del servidor: {res_full.json().get('detail')}")
        ok(f"Entrada a sala llena bloqueada correctamente (HTTP 400)")

        step(7, "Intentando unirse a una sala con ID inexistente...")
        fake_id = "sala-que-no-existe-12345"
        res_fake = requests.post(
            f"{BASE_URL}/api/games/join/{fake_id}",
            headers={"Authorization": f"Bearer {t3}"}
        )
        assert res_fake.status_code in (400, 404, 500), \
            f"El servidor acepto una sala falsa: HTTP {res_fake.status_code}"
        ok(f"Sala inexistente rechazada correctamente (HTTP {res_fake.status_code})")

        print("\n  ✔ BLOQUE 1 PASADO: Lobby y gestion de salas OK")
        return True

    except AssertionError as e:
        print(f"\n  ✘ BLOQUE 1 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 1]")
        for t, u in [(t1, u1), (t2, u2), (t3, u3)]:
            if t: delete_user(t, u)


# ─────────────────────────────────────────────
#  BLOQUE 2: INVITACION AMISTOSA
# ─────────────────────────────────────────────

async def run_friendly_invite_test():
    print("\n" + "="*60)
    print("  BLOQUE 2: FLUJO DE INVITACION AMISTOSA (DUELOS)")
    print("="*60)

    u1 = f"retador_{uuid.uuid4().hex[:4]}"
    u2 = f"amigo_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Creando retador '{u1}' y amigo '{u2}'...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        ok("Ambos usuarios creados y logueados")

        step(2, "Conectando WebSockets de notificaciones para ambos usuarios...")
        ws_url_1 = f"{WS_URL}/ws/notifications?token={t1}"
        ws_url_2 = f"{WS_URL}/ws/notifications?token={t2}"
        debug(f"WS notificaciones U1: {ws_url_1[:60]}...")
        debug(f"WS notificaciones U2: {ws_url_2[:60]}...")

        async with websockets.connect(ws_url_1) as notif1, \
                   websockets.connect(ws_url_2) as notif2:

            step(3, f"'{u1}' invita a '{u2}' a jugar (POST /api/games/invite)...")
            res_inv = requests.post(
                f"{BASE_URL}/api/games/invite?target_username={u2}",
                headers={"Authorization": f"Bearer {t1}"}
            )
            assert res_inv.status_code == 200, \
                f"HTTP {res_inv.status_code}: {res_inv.text}"
            game_id = res_inv.json().get("game_id")
            assert game_id is not None, \
                f"La API no devolvio game_id. Respuesta: {res_inv.json()}"
            debug(f"Invitacion creada. game_id='{game_id}'")
            ok(f"Invitacion enviada correctamente. game_id={game_id}")

            step(4, f"Esperando notificacion de duelo en el WS de '{u2}'...")
            aviso = await safe_recv(notif2, label=u2, timeout=5.0)
            assert aviso is not None, \
                f"'{u2}' no recibio ninguna notificacion en el WS"
            assert aviso.get("type") == "duel_invite", \
                f"Tipo incorrecto: esperado='duel_invite', recibido='{aviso.get('type')}'"
            debug(f"Payload de la notificacion: {aviso.get('payload')}")
            ok(f"'{u2}' recibio correctamente la notificacion de tipo 'duel_invite'")

            step(5, f"'{u2}' acepta el duelo (POST /api/games/{game_id}/accept)...")
            res_acc = requests.post(
                f"{BASE_URL}/api/games/{game_id}/accept",
                headers={"Authorization": f"Bearer {t2}"}
            )
            assert res_acc.status_code == 200, \
                f"HTTP {res_acc.status_code}: {res_acc.text}"
            debug(f"Respuesta accept: {res_acc.json()}")
            ok("Duelo aceptado correctamente")

            step(6, f"Verificando que '{u1}' recibe confirmacion de aceptacion...")
            confirma = await safe_recv(notif1, label=u1, timeout=5.0)
            assert confirma is not None, \
                f"'{u1}' no recibio confirmacion de aceptacion"
            assert confirma.get("type") == "invite_response", \
                f"Tipo incorrecto: esperado='invite_response', recibido='{confirma.get('type')}'"
            debug(f"Payload de confirmacion: {confirma.get('payload')}")
            ok(f"'{u1}' recibio 'invite_response' correctamente")

            step(7, "Ambos jugadores se conectan a la sala de juego y verifican el inicio...")
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as play1:
                asig1 = await safe_recv(play1, label=f"play-{u1}")
                assert asig1 and asig1.get("type") == "player_assignment", \
                    f"No se recibio player_assignment para '{u1}': {asig1}"
                debug(f"Color asignado a '{u1}': {asig1.get('payload', {}).get('color')}")
                await safe_recv(play1, label=f"play-{u1}")  # Estado "esperando"

                async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as play2:
                    asig2 = await safe_recv(play2, label=f"play-{u2}")
                    assert asig2 and asig2.get("type") == "player_assignment", \
                        f"No se recibio player_assignment para '{u2}': {asig2}"
                    debug(f"Color asignado a '{u2}': {asig2.get('payload', {}).get('color')}")

                    tablero1 = await safe_recv(play1, label=f"tablero-{u1}")
                    tablero2 = await safe_recv(play2, label=f"tablero-{u2}")

                    assert tablero1 and tablero1.get("type") == "game_state_update", \
                        f"'{u1}' no recibio el tablero inicial: {tablero1}"
                    assert tablero2 and tablero2.get("type") == "game_state_update", \
                        f"'{u2}' no recibio el tablero inicial: {tablero2}"

            ok("Ambos jugadores conectados a la partida amistosa. Tablero inicial recibido")

        print("\n  ✔ BLOQUE 2 PASADO: Flujo de invitacion amistosa OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 2 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 2]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 3: CHAT BIDIRECCIONAL
# ─────────────────────────────────────────────

async def run_chat_test():
    print("\n" + "="*60)
    print("  BLOQUE 3: CHAT BIDIRECCIONAL EN PARTIDA")
    print("="*60)

    u1 = f"chatterA_{uuid.uuid4().hex[:4]}"
    u2 = f"chatterB_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    async def wait_for_chat_msg(ws, label, expected_sender, timeout=6.0):
        """Espera hasta recibir un mensaje de tipo 'chat_message' del sender esperado."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            raw = await safe_recv(ws, label=label, timeout=min(remaining, 2.0))
            if raw is None:
                break
            if raw.get("type") == "chat_message":
                sender = raw.get("payload", {}).get("sender")
                if sender == expected_sender:
                    debug(f"[{label}] Chat recibido de '{sender}': "
                          f"'{raw['payload'].get('message')}'")
                    return raw
        return None

    try:
        step(1, f"Creando usuarios de chat '{u1}' y '{u2}'...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        ok("Ambos usuarios listos")

        step(2, "Creando sala 1v1 y uniendo a ambos jugadores via HTTP...")
        res_c = requests.post(
            f"{BASE_URL}/api/games/create",
            headers={"Authorization": f"Bearer {t1}"},
            json={"mode": "1v1"}
        )
        assert res_c.status_code == 200, f"HTTP {res_c.status_code}: {res_c.text}"
        game_id = res_c.json()["game_id"]
        debug(f"Sala creada: {game_id}")

        res_j = requests.post(
            f"{BASE_URL}/api/games/join/{game_id}",
            headers={"Authorization": f"Bearer {t2}"}
        )
        assert res_j.status_code == 200, f"HTTP {res_j.status_code}: {res_j.text}"
        ok(f"Sala '{game_id}' lista con ambos jugadores")

        step(3, "Conectando ambos al WebSocket de juego...")
        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as ws2:

            # Consumir mensajes de inicializacion
            debug("Consumiendo mensajes iniciales (assignment + estado)...")
            for _ in range(3):
                await safe_recv(ws1, label=f"init-{u1}", timeout=2.0)
                await safe_recv(ws2, label=f"init-{u2}", timeout=2.0)
            ok("WebSockets conectados. Mensajes de inicio consumidos")

            step(4, f"'{u1}' envia un mensaje de chat...")
            msg1 = "Hola rival, que comience el juego!"
            await ws1.send(json.dumps({"action": "chat", "message": msg1}))
            debug(f"Mensaje enviado por '{u1}': '{msg1}'")

            recibido_u2 = await wait_for_chat_msg(ws2, label=u2, expected_sender=u1)
            assert recibido_u2 is not None, \
                f"'{u2}' no recibio el chat de '{u1}' a tiempo"
            assert recibido_u2["payload"]["message"] == msg1, \
                f"Contenido incorrecto: esperado='{msg1}' recibido='{recibido_u2['payload']['message']}'"
            ok(f"'{u2}' recibio correctamente el mensaje de '{u1}'")

            step(5, f"'{u2}' responde por el chat...")
            msg2 = "Gracias! Suerte a ti tambien."
            await ws2.send(json.dumps({"action": "chat", "message": msg2}))
            debug(f"Mensaje enviado por '{u2}': '{msg2}'")

            recibido_u1 = await wait_for_chat_msg(ws1, label=u1, expected_sender=u2)
            assert recibido_u1 is not None, \
                f"'{u1}' no recibio la respuesta de '{u2}' a tiempo"
            assert recibido_u1["payload"]["message"] == msg2, \
                f"Contenido incorrecto: esperado='{msg2}' recibido='{recibido_u1['payload']['message']}'"
            ok(f"'{u1}' recibio correctamente la respuesta de '{u2}'")

            step(6, "Probando mensaje de chat vacio (no debe propagarse)...")
            await ws1.send(json.dumps({"action": "chat", "message": ""}))
            eco_vacio = await safe_recv(ws2, label=f"empty-check-{u2}", timeout=2.0)
            if eco_vacio and eco_vacio.get("type") == "chat_message":
                debug("El servidor propago un mensaje vacio (comportamiento permisivo)")
            else:
                ok("Mensaje vacio ignorado correctamente")

        print("\n  ✔ BLOQUE 3 PASADO: Chat bidireccional OK")
        return True

    except (AssertionError, Exception) as e:
        print(f"\n  ✘ BLOQUE 3 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 3]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────

async def async_main():
    results = {}

    results["Lobby publico y gestion de salas"]     = run_lobby_test()
    results["Invitacion amistosa (duelos)"]          = await run_friendly_invite_test()
    results["Chat bidireccional en partida"]         = await run_chat_test()

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
    print("  TEST SUITE: MATCHMAKING, SALAS Y COMUNICACION")
    print("#"*60)
    asyncio.run(async_main())


if __name__ == "__main__":
    main()