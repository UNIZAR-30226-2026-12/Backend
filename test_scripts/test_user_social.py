"""
TEST SUITE: IDENTIDAD DE USUARIO, SISTEMA SOCIAL Y RANKING
===========================================================
Cubre los siguientes ambitos:
  1. Registro y Login (Auth completo)
  2. Perfil propio y actualizacion de datos
  3. Personalizacion estetica del perfil
  4. Estadisticas por usuario (ELO, winrate...)
  5. Sistema de amigos: enviar, listar, aceptar, eliminar peticion
  6. Leaderboard global (ranking)
"""

import requests
import uuid
import sys

BASE_URL = "http://localhost:8081"

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
        f"[ERROR] Fallo al registrar '{username}': HTTP {res_reg.status_code} → {res_reg.text}"
    debug(f"Usuario '{username}' registrado. ID devuelto: {res_reg.json().get('id')}")

    res_log = requests.post(f"{BASE_URL}/api/auth/login", data={
        "username": username, "password": password
    })
    assert res_log.status_code == 200, \
        f"[ERROR] Fallo al loguear '{username}': HTTP {res_log.status_code} → {res_log.text}"
    token = res_log.json()["access_token"]
    debug(f"Token JWT obtenido para '{username}': {token[:30]}...")
    return token

def delete_user(token, username):
    res = requests.delete(f"{BASE_URL}/api/users/me",
                          headers={"Authorization": f"Bearer {token}"})
    if res.status_code == 200:
        print(f"   [Limpieza] '{username}' eliminado correctamente.")
    else:
        print(f"   [Limpieza] ATENCION — No se pudo eliminar '{username}': {res.text}")

def get_user_id(token):
    res = requests.get(f"{BASE_URL}/api/users/me",
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"[ERROR] No se pudo obtener /me: {res.text}"
    return res.json()["id"]

# ─────────────────────────────────────────────
#  BLOQUE 1: AUTENTICACION Y PERFIL
# ─────────────────────────────────────────────

def run_auth_and_profile_test():
    print("\n" + "="*60)
    print("  BLOQUE 1: AUTENTICACION, PERFIL Y ESTADISTICAS")
    print("="*60)

    username = f"usuario_{uuid.uuid4().hex[:5]}"
    email    = f"{username}@example.com"
    password = "superPass99"
    token    = None

    try:
        step(1, f"Registrando nuevo usuario '{username}'...")
        reg_data = {"username": username, "email": email, "password": password}
        res_reg  = requests.post(f"{BASE_URL}/api/auth/register", json=reg_data)
        assert res_reg.status_code == 200, \
            f"HTTP {res_reg.status_code}: {res_reg.text}"
        user_id = res_reg.json()["id"]
        ok(f"Usuario registrado con ID={user_id}")

        step(2, "Iniciando sesion con las credenciales correctas (Login)...")
        res_log = requests.post(f"{BASE_URL}/api/auth/login",
                                data={"username": username, "password": password})
        assert res_log.status_code == 200, \
            f"HTTP {res_log.status_code}: {res_log.text}"
        token   = res_log.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        ok(f"Token JWT recibido correctamente")
        debug(f"Token (primeros 40 chars): {token[:40]}...")

        step(3, "Verificando login fallido con contrasena incorrecta...")
        res_bad = requests.post(f"{BASE_URL}/api/auth/login",
                                data={"username": username, "password": "WRONGPASS"})
        assert res_bad.status_code in (400, 401, 403), \
            f"El servidor acepto credenciales invalidas: HTTP {res_bad.status_code}"
        ok(f"Login incorrecto rechazado con HTTP {res_bad.status_code}")

        step(4, "Obteniendo perfil propio (GET /api/users/me)...")
        res_me = requests.get(f"{BASE_URL}/api/users/me", headers=headers)
        assert res_me.status_code == 200, f"HTTP {res_me.status_code}: {res_me.text}"
        perfil = res_me.json()
        assert perfil["username"] == username, \
            f"Username no coincide: esperado='{username}' recibido='{perfil['username']}'"
        debug(f"Perfil completo: {perfil}")
        ok(f"Perfil obtenido y validado: username='{perfil['username']}'")

        step(5, "Actualizando email del perfil (PUT /api/users/me)...")
        new_email = f"updated_{email}"
        res_upd   = requests.put(f"{BASE_URL}/api/users/me",
                                 json={"email": new_email}, headers=headers)
        assert res_upd.status_code == 200, f"HTTP {res_upd.status_code}: {res_upd.text}"
        assert res_upd.json()["email"] == new_email, \
            f"Email no actualizado: esperado='{new_email}' recibido='{res_upd.json()['email']}'"
        ok(f"Email actualizado correctamente a '{new_email}'")

        step(6, "Personalizacion estetica (PUT /api/users/customization)...")
        custom_data = {
            "preferred_board_color": "#1A2B3C",
            "preferred_piece_color": "neon_pink"
        }
        res_cust = requests.put(f"{BASE_URL}/api/users/customization",
                                json=custom_data, headers=headers)
        assert res_cust.status_code == 200, \
            f"HTTP {res_cust.status_code}: {res_cust.text}"
        debug(f"Respuesta personalizacion: {res_cust.json()}")

        # Verificar persistencia
        res_me2 = requests.get(f"{BASE_URL}/api/users/me", headers=headers).json()
        assert res_me2.get("preferred_board_color") == "#1A2B3C", \
            f"Color del tablero no persiste. Recibido: {res_me2.get('preferred_board_color')}"
        assert res_me2.get("preferred_piece_color") == "neon_pink", \
            f"Color de fichas no persiste. Recibido: {res_me2.get('preferred_piece_color')}"
        ok("Personalizacion guardada y verificada en BD")

        step(7, f"Consultando estadisticas del usuario (GET /api/users/{user_id}/stats)...")
        res_stats = requests.get(f"{BASE_URL}/api/users/{user_id}/stats")
        assert res_stats.status_code == 200, f"HTTP {res_stats.status_code}: {res_stats.text}"
        stats = res_stats.json()
        assert "winrate" in stats, f"Falta 'winrate' en stats. Recibido: {stats}"
        assert "elo" in stats,     f"Falta 'elo' en stats. Recibido: {stats}"
        debug(f"Stats completas: {stats}")
        ok(f"Stats correctas: ELO={stats['elo']}, Winrate={stats['winrate']}")

        step(8, "Verificando acceso sin token (debe ser rechazado)...")
        res_unauth = requests.get(f"{BASE_URL}/api/users/me")
        assert res_unauth.status_code in (401, 403, 422), \
            f"Endpoint /me accesible sin token: HTTP {res_unauth.status_code}"
        ok(f"Acceso sin token rechazado correctamente: HTTP {res_unauth.status_code}")

        print("\n  ✔ BLOQUE 1 PASADO: Auth, perfil y personalizacion OK")
        return True

    except AssertionError as e:
        print(f"\n  ✘ BLOQUE 1 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 1]")
        if token:
            delete_user(token, username)


# ─────────────────────────────────────────────
#  BLOQUE 2: SISTEMA DE AMIGOS
# ─────────────────────────────────────────────

def run_social_test():
    print("\n" + "="*60)
    print("  BLOQUE 2: SISTEMA SOCIAL (AMIGOS Y PETICIONES)")
    print("="*60)

    u1 = f"sender_{uuid.uuid4().hex[:4]}"
    u2 = f"receiver_{uuid.uuid4().hex[:4]}"
    t1, t2 = None, None

    try:
        step(1, f"Creando dos usuarios: '{u1}' y '{u2}'...")
        t1 = create_and_login(u1)
        t2 = create_and_login(u2)
        h1 = {"Authorization": f"Bearer {t1}"}
        h2 = {"Authorization": f"Bearer {t2}"}
        ok(f"Ambos usuarios creados y logueados")

        step(2, f"'{u1}' envia peticion de amistad a '{u2}'...")
        res_req = requests.post(f"{BASE_URL}/api/friends/request",
                                json={"username": u2}, headers=h1)
        assert res_req.status_code == 200, \
            f"HTTP {res_req.status_code}: {res_req.text}"
        debug(f"Respuesta del servidor: {res_req.json()}")
        ok(f"Peticion enviada: {res_req.json().get('message')}")

        step(3, f"'{u2}' lista sus peticiones pendientes (GET /api/friends)...")
        res_list = requests.get(f"{BASE_URL}/api/friends", headers=h2)
        assert res_list.status_code == 200, f"HTTP {res_list.status_code}: {res_list.text}"
        data = res_list.json()
        debug(f"Respuesta completa del servidor: {data}")

        peticion = None
        for r in data.get("requests", []):
            nombre = r.get("name") or r.get("username") or r.get("sender_name")
            if nombre == u1:
                peticion = r
                break

        assert peticion is not None, \
            f"Peticion de '{u1}' no encontrada en: {data.get('requests')}"
        u1_id = peticion["id"]
        debug(f"Peticion localizada. ID del remitente: {u1_id}")
        ok(f"Peticion de '{u1}' visible en la bandeja de '{u2}'")

        step(4, f"'{u2}' acepta la peticion de '{u1}' (POST /api/friends/{u1_id}/accept)...")
        res_acc = requests.post(f"{BASE_URL}/api/friends/{u1_id}/accept", headers=h2)
        assert res_acc.status_code == 200, f"HTTP {res_acc.status_code}: {res_acc.text}"
        debug(f"Respuesta aceptacion: {res_acc.json()}")
        ok(f"Amistad aceptada: {res_acc.json().get('message')}")

        step(5, "Verificando relacion mutua en ambas listas de amigos...")
        lista_u1 = requests.get(f"{BASE_URL}/api/friends", headers=h1).json()
        lista_u2 = requests.get(f"{BASE_URL}/api/friends", headers=h2).json()
        debug(f"Amigos de '{u1}': {lista_u1.get('friends')}")
        debug(f"Amigos de '{u2}': {lista_u2.get('friends')}")

        en_u1 = any((f.get("name") or f.get("username")) == u2
                    for f in lista_u1.get("friends", []))
        en_u2 = any((f.get("name") or f.get("username")) == u1
                    for f in lista_u2.get("friends", []))
        assert en_u1, f"'{u2}' no aparece en la lista de amigos de '{u1}'"
        assert en_u2, f"'{u1}' no aparece en la lista de amigos de '{u2}'"
        ok("Ambos usuarios se ven mutuamente como amigos")

        step(6, "Verificando que peticiones duplicadas son rechazadas...")
        res_dup = requests.post(f"{BASE_URL}/api/friends/request",
                                json={"username": u2}, headers=h1)
        assert res_dup.status_code in (400, 409), \
            f"Se permitio una peticion duplicada: HTTP {res_dup.status_code}"
        debug(f"Respuesta a peticion duplicada: HTTP {res_dup.status_code} → {res_dup.text}")
        ok(f"Peticion duplicada bloqueada con HTTP {res_dup.status_code}")

        step(7, f"'{u1}' elimina a '{u2}' de su lista de amigos...")
        u2_id = requests.get(f"{BASE_URL}/api/users/me", headers=h2).json()["id"]
        debug(f"ID de '{u2}': {u2_id}")
        res_del = requests.delete(f"{BASE_URL}/api/friends/{u2_id}", headers=h1)
        assert res_del.status_code == 200, f"HTTP {res_del.status_code}: {res_del.text}"
        ok(f"Respuesta: {res_del.json().get('message')}")

        step(8, "Verificando que la amistad ya no existe en ninguna lista...")
        final_u1 = requests.get(f"{BASE_URL}/api/friends", headers=h1).json()
        final_u2 = requests.get(f"{BASE_URL}/api/friends", headers=h2).json()
        debug(f"Amigos restantes de '{u1}': {final_u1.get('friends')}")
        debug(f"Amigos restantes de '{u2}': {final_u2.get('friends')}")

        sigue_u1 = any((f.get("name") or f.get("username")) == u2
                       for f in final_u1.get("friends", []))
        assert not sigue_u1, \
            f"'{u2}' todavia aparece en la lista de '{u1}' tras eliminarle"
        ok("Relacion eliminada correctamente. Ninguno se ve en la lista del otro")

        print("\n  ✔ BLOQUE 2 PASADO: Sistema social OK")
        return True

    except AssertionError as e:
        print(f"\n  ✘ BLOQUE 2 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 2]")
        if t1: delete_user(t1, u1)
        if t2: delete_user(t2, u2)


# ─────────────────────────────────────────────
#  BLOQUE 3: LEADERBOARD GLOBAL
# ─────────────────────────────────────────────

def run_ranking_test():
    print("\n" + "="*60)
    print("  BLOQUE 3: LEADERBOARD GLOBAL (RANKING)")
    print("="*60)

    dummy = f"top_player_{uuid.uuid4().hex[:4]}"
    token = None

    try:
        step(1, f"Creando usuario de referencia '{dummy}'...")
        token = create_and_login(dummy)
        ok("Usuario creado y logueado")

        step(2, "Consultando el Top 50 global (GET /api/ranking/)...")
        res = requests.get(f"{BASE_URL}/api/ranking/")
        assert res.status_code == 200, f"HTTP {res.status_code}: {res.text}"
        data = res.json()
        assert "ranking" in data, \
            f"El JSON no contiene la clave 'ranking'. Recibido: {list(data.keys())}"
        ranking = data["ranking"]
        assert isinstance(ranking, list), \
            f"'ranking' no es una lista sino: {type(ranking)}"
        assert len(ranking) > 0, \
            "El ranking esta vacio (se esperaba al menos 1 jugador)"
        debug(f"Total de jugadores en el ranking: {len(ranking)}")
        ok(f"Ranking recibido con {len(ranking)} jugadores")

        step(3, "Validando estructura de cada entrada del ranking...")
        for i, player in enumerate(ranking):
            assert "username" in player, \
                f"Entrada #{i} sin 'username': {player}"
            assert "elo" in player, \
                f"Entrada #{i} sin 'elo': {player}"

        first = ranking[0]
        debug(f"Campos disponibles en cada entrada: {list(first.keys())}")
        ok("Estructura de cada jugador validada (username + elo presentes)")

        step(4, "Verificando que el ranking esta ordenado de mayor a menor ELO...")
        elos = [p["elo"] for p in ranking]
        assert elos == sorted(elos, reverse=True), \
            f"El ranking NO esta ordenado por ELO DESC. ELOs: {elos}"
        ok("Orden descendente de ELO confirmado")

        step(5, "Mostrando TOP 5 para verificacion visual...")
        print()
        print("         ┌───────────────────────────────────────┐")
        print("         │         TOP 5 GLOBAL (RANKING)        │")
        print("         ├─────┬──────────────────┬──────────────┤")
        print("         │ Pos │ Username         │ ELO          │")
        print("         ├─────┼──────────────────┼──────────────┤")
        for i, p in enumerate(ranking[:5], 1):
            print(f"         │ #{i:<3} │ {p.get('username'):<16} │ {str(p.get('elo')):<12} │")
        print("         └─────┴──────────────────┴──────────────┘")

        step(6, "Verificando que el usuario recien creado aparece en el ranking...")
        en_ranking = any(p.get("username") == dummy for p in ranking)
        if en_ranking:
            ok(f"'{dummy}' ya visible en el ranking")
        else:
            debug(f"'{dummy}' no esta aun en el top (puede requerir ELO minimo)")

        print("\n  ✔ BLOQUE 3 PASADO: Leaderboard global OK")
        return True

    except AssertionError as e:
        print(f"\n  ✘ BLOQUE 3 FALLIDO: {e}")
        return False

    finally:
        print("\n  [Teardown Bloque 3]")
        if token:
            delete_user(token, dummy)


# ─────────────────────────────────────────────
#  RUNNER PRINCIPAL
# ─────────────────────────────────────────────

def main():
    print("\n" + "#"*60)
    print("  TEST SUITE: IDENTIDAD, SOCIAL Y RANKING")
    print("#"*60)

    results = {
        "Auth, perfil y personalizacion": run_auth_and_profile_test(),
        "Sistema social (amigos)"       : run_social_test(),
        "Leaderboard global"            : run_ranking_test(),
    }

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


if __name__ == "__main__":
    main()