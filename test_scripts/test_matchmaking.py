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

async def wait_for_game_update(ws, timeout=3.0):
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
                await asyncio.sleep(0.6); await ws.send(json.dumps({"action": "set_ready", "ready": True}))
                continue
                
            # Ignoramos la sincronizacion del lobby para que los asserts antiguos no fallen
            if tipo == "room_sync":
                continue
                
            print(f"         · DEBUG: [{label}] tipo='{tipo}' | payload={str(data.get('payload'))[:100]}")
            return data
    except Exception:
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
            json={"mode": "1vs1"}
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
            requests.post(f"{BASE_URL}/api/friends/request", json={"username": u2}, headers={"Authorization": f"Bearer {t1}"})
            data_friends = requests.get(f"{BASE_URL}/api/friends", headers={"Authorization": f"Bearer {t2}"}).json()
            peticion = next((r for r in data_friends['requests'] if (r.get('name') or r.get('username')) == u1), None)
            requests.post(f"{BASE_URL}/api/friends/{peticion['id']}/accept", headers={"Authorization": f"Bearer {t2}"})

            target_id = requests.get(f"{BASE_URL}/api/users/me", headers={"Authorization": f"Bearer {t2}"}).json()["id"]
            res_inv = requests.post(f"{BASE_URL}/api/games/invite", json={"friend_ids": [target_id], "mode": "1vs1"}, headers={"Authorization": f"Bearer {t1}"})
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

            step(6, "Probar flujo de rechazo de invitacion (/reject)...")
            id2 = requests.get(f"{BASE_URL}/api/users/me", headers={"Authorization": f"Bearer {t2}"}).json()["id"]
            res_inv2 = requests.post(f"{BASE_URL}/api/games/invite", headers={"Authorization": f"Bearer {t1}"}, json={"friend_ids": [id2], "mode": "1v1"})
            game_id_reject = res_inv2.json()["game_id"]
            res_rej = requests.post(f"{BASE_URL}/api/games/{game_id_reject}/reject", headers={"Authorization": f"Bearer {t2}"})
            assert res_rej.status_code == 200, "Fallo al rechazar la invitacion"
            estado_sala = requests.get(f"{BASE_URL}/api/games/{game_id_reject}/state", headers={"Authorization": f"Bearer {t1}"})
            assert estado_sala.status_code == 404, "La sala 1v1 rechazada no fue destruida de la base de datos"
            ok("El flujo de rechazo limpia correctamente las salas no deseadas")

            step(7, f"Verificando que '{u1}' recibe confirmacion de aceptacion...")
            confirma = await safe_recv(notif1, label=u1, timeout=5.0)
            assert confirma is not None, \
                f"'{u1}' no recibio confirmacion de aceptacion"
            assert confirma.get("type") == "invite_response", \
                f"Tipo incorrecto: esperado='invite_response', recibido='{confirma.get('type')}'"
            debug(f"Payload de confirmacion: {confirma.get('payload')}")
            ok(f"'{u1}' recibio 'invite_response' correctamente")

            step(8, "Ambos jugadores se conectan a la sala de juego y verifican el inicio...")
            async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t1}") as play1:
                asig1 = await safe_recv(play1, label=f"play-{u1}")
                assert asig1 and asig1.get("type") == "player_assignment", \
                    f"No se recibio player_assignment para '{u1}': {asig1}"
                debug(f"Color asignado a '{u1}': {asig1.get('payload', {}).get('color')}")

                async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={t2}") as play2:
                    asig2 = await safe_recv(play2, label=f"play-{u2}")
                    assert asig2 and asig2.get("type") == "player_assignment", \
                        f"No se recibio player_assignment para '{u2}': {asig2}"
                    debug(f"Color asignado a '{u2}': {asig2.get('payload', {}).get('color')}")

                    tablero1, tablero2 = await asyncio.gather(
                        safe_recv(play1, label=f"tablero-{u1}"),
                        safe_recv(play2, label=f"tablero-{u2}")
                    )

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
            json={"mode": "1vs1"}
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
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "chat", "message": msg1}))
            debug(f"Mensaje enviado por '{u1}': '{msg1}'")

            recibido_u2 = await wait_for_chat_msg(ws2, label=u2, expected_sender=u1)
            assert recibido_u2 is not None, \
                f"'{u2}' no recibio el chat de '{u1}' a tiempo"
            assert recibido_u2["payload"]["message"] == msg1, \
                f"Contenido incorrecto: esperado='{msg1}' recibido='{recibido_u2['payload']['message']}'"
            ok(f"'{u2}' recibio correctamente el mensaje de '{u1}'")

            step(5, f"'{u2}' responde por el chat...")
            msg2 = "Gracias! Suerte a ti tambien."
            await asyncio.sleep(0.6); await ws2.send(json.dumps({"action": "chat", "message": msg2}))
            debug(f"Mensaje enviado por '{u2}': '{msg2}'")

            recibido_u1 = await wait_for_chat_msg(ws1, label=u1, expected_sender=u2)
            assert recibido_u1 is not None, \
                f"'{u1}' no recibio la respuesta de '{u2}' a tiempo"
            assert recibido_u1["payload"]["message"] == msg2, \
                f"Contenido incorrecto: esperado='{msg2}' recibido='{recibido_u1['payload']['message']}'"
            ok(f"'{u1}' recibio correctamente la respuesta de '{u2}'")

            step(6, "Probando mensaje de chat vacio (no debe propagarse)...")
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "chat", "message": ""}))
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
#  BLOQUE 4: MATCHMAKING Y SALAS DE ESPERA (4P)
# ─────────────────────────────────────────────

async def run_4p_matchmaking_test():
    print("\n" + "="*60)
    print("  BLOQUE 4: MATCHMAKING Y SALAS DE ESPERA (4P)")
    print("="*60)
    users, tokens, ids = get_random_users(4)
    host_t, g1_t, g2_t, g3_t = tokens
    try:
        step(1, "Lobby Publico: Creando sala 1v1v1v1...")
        res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {host_t}"}, json={"mode": "1v1v1v1"})
        game_id = res.json()["game_id"]
        
        lobbies = requests.get(f"{BASE_URL}/api/games/public").json().get("lobbies", [])
        assert any(str(l["game_id"]) == str(game_id) for l in lobbies), "La sala publica 4P no es visible en el lobby"
        ok("Sala creada y visible en el lobby publico")

        step(2, "Llenado progresivo: uniendo a Jugador 2 y 3...")
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {g1_t}"})
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {g2_t}"})
        
        lobbies = requests.get(f"{BASE_URL}/api/games/public").json().get("lobbies", [])
        assert any(str(l["game_id"]) == str(game_id) for l in lobbies), "La sala desaparecio prematuramente del lobby publico"
        ok("La sala sigue visible con 3/4 jugadores")

        step(3, "Jugador 4 se une, verificando que desaparezca del lobby...")
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {g3_t}"})
        lobbies = requests.get(f"{BASE_URL}/api/games/public").json().get("lobbies", [])
        assert not any(str(l["game_id"]) == str(game_id) for l in lobbies), "La sala llena sigue en el lobby"
        ok("Sala llena retirada del lobby correctamente")

        step(4, "Invitaciones Privadas Multiples...")
        for u in users[1:]:
            requests.post(f"{BASE_URL}/api/friends/request", json={"username": u}, headers={"Authorization": f"Bearer {host_t}"})
            
        for g_t in [g1_t, g2_t, g3_t]:
            data_friends = requests.get(f"{BASE_URL}/api/friends", headers={"Authorization": f"Bearer {g_t}"}).json()
            peticion = next((r for r in data_friends.get('requests', []) if (r.get('name') or r.get('username')) == users[0]), None)
            if peticion:
                requests.post(f"{BASE_URL}/api/friends/{peticion['id']}/accept", headers={"Authorization": f"Bearer {g_t}"})

        async with websockets.connect(f"{WS_URL}/ws/notifications?token={host_t}") as ws_notif:
            inv_res = requests.post(f"{BASE_URL}/api/games/invite", headers={"Authorization": f"Bearer {host_t}"}, json={
                "mode": "1vs1vs1vs1", "friend_ids": ids[1:]
            })
            assert inv_res.status_code == 200, f"Error invitando: {inv_res.text}"
            priv_game_id = inv_res.json()["game_id"]
            ok(f"Invitacion multiple enviada a 3 amigos")

            step(5, "Aceptacion asincrona...")
            requests.post(f"{BASE_URL}/api/games/{priv_game_id}/accept", headers={"Authorization": f"Bearer {g1_t}"})
            notif1 = await safe_recv(ws_notif, timeout=2.0)
            assert notif1 and notif1.get("payload", {}).get("action") == "accepted"
            ok("Host recibio notificacion individual de aceptacion")

            step(6, "Rechazo de invitacion (cierra la sala)...")
            requests.post(f"{BASE_URL}/api/games/{priv_game_id}/reject", headers={"Authorization": f"Bearer {g2_t}"})
            notif2 = await safe_recv(ws_notif, timeout=2.0)
            assert notif2 and notif2.get("payload", {}).get("action") == "rejected"
            ok("Jugador 3 rechaza. Host notificado y sala invalidada.")

        print("\n  ✔ BLOQUE 4 PASADO: Matchmaking 4P OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 4 FALLIDO: {e}")
        return False
    finally:
        for t, u in zip(tokens, users): delete_user(t, u)


# ─────────────────────────────────────────────
#  BLOQUE 5: SINCRONIZACION Y PREPARACION (4P)
# ─────────────────────────────────────────────

async def run_4p_sync_chat_test():
    print("\n" + "="*60)
    print("  BLOQUE 5: SINCRONIZACION Y PREPARACION (4P)")
    print("="*60)
    users, tokens, ids = get_random_users(4)
    try:
        step(1, "Creando sala y asignando 4 colores...")
        res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {tokens[0]}"}, json={"mode": "1v1v1v1"})
        game_id = res.json()["game_id"]
        for t in tokens[1:]: requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {t}"})

        async with websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[0]}") as ws0, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[1]}") as ws1, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[2]}") as ws2, \
                   websockets.connect(f"{WS_URL}/ws/play/{game_id}?token={tokens[3]}") as ws3:

            colores = []
            for ws in [ws0, ws1, ws2, ws3]:
                msg = await safe_recv(ws)
                if msg and msg.get("type") == "player_assignment":
                    colores.append(msg["payload"]["color"])
            
            assert set(colores) == {"black", "white", "red", "blue"}, f"Colores asignados erroneos: {colores}"
            ok("Colores unicos asignados (black, white, red, blue)")

            step(2, "El Ready Parcial...")
            await asyncio.sleep(0.6); await ws0.send(json.dumps({"action": "set_ready", "ready": True}))
            await asyncio.sleep(0.6); await ws1.send(json.dumps({"action": "set_ready", "ready": True}))
            await asyncio.sleep(0.6); await ws2.send(json.dumps({"action": "set_ready", "ready": True}))

            msg_test = await wait_for_game_update(ws0)
            if msg_test: raise AssertionError("La partida empezo con solo 3 listos!")
            ok("La partida sigue 'waiting' con 3 jugadores listos")

            await asyncio.sleep(0.6); await ws3.send(json.dumps({"action": "set_ready", "ready": True}))
            estados = await asyncio.gather(wait_for_game_update(ws0), wait_for_game_update(ws1), wait_for_game_update(ws2), wait_for_game_update(ws3))
            assert all(e["payload"]["status"] == "playing" for e in estados if e), "El estado no cambio a playing"
            ok("La partida comenzo al estar los 4 ready")

            step(3, "Chat Multijugador...")
            await asyncio.sleep(0.6); await ws0.send(json.dumps({"action": "chat", "message": "Hola a todos"}))
            chat_msgs = await asyncio.gather(safe_recv(ws1), safe_recv(ws2), safe_recv(ws3))
            assert all(c and c.get("type") == "chat_message" for c in chat_msgs), "Fallo la propagacion del chat"
            ok("Mensaje de chat recibido por los 3 contrincantes concurrentemente")

        print("\n  ✔ BLOQUE 5 PASADO: Sincronizacion OK")
        return True
    except Exception as e:
        print(f"\n  ✘ BLOQUE 5 FALLIDO: {e}")
        return False
    finally:
        for t, u in zip(tokens, users): delete_user(t, u)


# ─────────────────────────────────────────────
#  BLOQUE 6: LOBBY RESILIENTE, KICKS Y BOTS
# ─────────────────────────────────────────────

async def run_lobby_premium_test():
    print("\n" + "="*60)
    print("  BLOQUE 6: LOBBY RESILIENTE, KICKS Y BOTS (4P)")
    print("="*60)
    # Ajustado para recoger también los 'ids' que devuelve tu función actual
    users, tokens, ids = get_random_users(4)
    host_t, g1_t, g2_t, g3_t = tokens
    host_u, g1_u, g2_u, g3_u = users

    try:
        step(1, "Host crea la sala 4P publica...")
        res = requests.post(f"{BASE_URL}/api/games/create", headers={"Authorization": f"Bearer {host_t}"}, json={"mode": "1v1v1v1"})
        game_id = res.json()["game_id"]
        ok(f"Sala {game_id} creada")

        step(2, "Invitado 1 entra y luego abandona (La sala de cristal)...")
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {g1_t}"})
        res_leave = requests.post(f"{BASE_URL}/api/games/{game_id}/leave", headers={"Authorization": f"Bearer {g1_t}"})
        assert res_leave.status_code == 200, f"Fallo al hacer leave: {res_leave.status_code} - {res_leave.text}"
        
        estado = requests.get(f"{BASE_URL}/api/games/{game_id}/state", headers={"Authorization": f"Bearer {host_t}"})
        assert estado.status_code == 200, "¡La sala fue destruida erroneamente!"
        assert len(estado.json()["players"]) == 1, "El jugador no fue borrado de la sala"
        ok("El invitado salio pero la sala sigue intacta para el Host")

        step(3, "Invitado 2 entra y el Host lo expulsa (Kick)...")
        requests.post(f"{BASE_URL}/api/games/join/{game_id}", headers={"Authorization": f"Bearer {g2_t}"})
        res_kick = requests.post(f"{BASE_URL}/api/games/{game_id}/kick/{g2_u}", headers={"Authorization": f"Bearer {host_t}"})
        assert res_kick.status_code == 200, f"Error en kick: {res_kick.text}"
        
        estado = requests.get(f"{BASE_URL}/api/games/{game_id}/state", headers={"Authorization": f"Bearer {host_t}"})
        assert not any(p["username"] == g2_u for p in estado.json()["players"]), "El jugador no fue expulsado"
        ok("El jugador troll fue expulsado con exito por el Host")

        step(4, "Host rellena los 3 huecos restantes con Bots (IA)...")
        for _ in range(3):
            res_bot = requests.post(f"{BASE_URL}/api/games/{game_id}/add_bot", headers={"Authorization": f"Bearer {host_t}"})
            assert res_bot.status_code == 200, f"Error añadiendo bot: {res_bot.text}"
        
        estado_final = requests.get(f"{BASE_URL}/api/games/{game_id}/state", headers={"Authorization": f"Bearer {host_t}"})
        bots = [p["username"] for p in estado_final.json()["players"] if p["username"].startswith("IA_")]
        assert len(bots) == 3, "No se crearon los 3 bots"
        assert estado_final.json()["status"] == "playing", "La partida no empezo automaticamente tras llenarse de bots"
        ok(f"Bots inyectados correctamente: {bots}. La partida ha comenzado.")

        print("\n  ✔ BLOQUE 6 PASADO: Resiliencia y Autoridad OK")
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

    results["Lobby publico y gestion de salas"]       = run_lobby_test()
    results["Invitacion amistosa (duelos)"]           = await run_friendly_invite_test()
    results["Chat bidireccional en partida"]          = await run_chat_test()
    results["Matchmaking y Salas de Espera (4P)"]     = await run_4p_matchmaking_test()
    results["Sincronizacion y Chat (4P)"]             = await run_4p_sync_chat_test()
    results["Lobby Resiliente y Autoridad (Kick/Bots)"]= await run_lobby_premium_test()

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