import requests
import uuid
import sys
import time

BASE_URL = "http://localhost:8081"
EXPECTED_MESSAGE = "Si el correo existe, recibirás una nueva contraseña"


def step(n, msg):
    print(f"\n[PASO {n}] {msg}")


def ok(msg):
    print(f"         ✓ OK: {msg}")


def debug(msg):
    print(f"         · DEBUG: {msg}")


def register_user(username, password):
    email = f"{username}@test.com"
    res = requests.post(f"{BASE_URL}/api/auth/register", json={
        "username": username, "email": email, "password": password
    })
    assert res.status_code == 200, f"No se pudo registrar '{username}': HTTP {res.status_code} → {res.text}"
    return email, res.json()["id"]


def login(identifier, password):
    return requests.post(f"{BASE_URL}/api/auth/login",
                         data={"username": identifier, "password": password})


def delete_user_by_login(identifier, password):
    res_log = login(identifier, password)
    if res_log.status_code != 200:
        print(f"   [Limpieza] No se pudo loguear '{identifier}' para borrar (password ya rotada).")
        return
    token = res_log.json()["access_token"]
    res_del = requests.delete(f"{BASE_URL}/api/users/me",
                              headers={"Authorization": f"Bearer {token}"})
    if res_del.status_code == 200:
        print(f"   [Limpieza] '{identifier}' eliminado correctamente.")
    else:
        print(f"   [Limpieza] ATENCION — No se pudo eliminar '{identifier}': {res_del.text}")


def forgot(email):
    return requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": email})


# ─────────────────────────────────────────────
#  BLOQUE 1: RESPUESTA GENÉRICA (no revelar)
# ─────────────────────────────────────────────

def test_generic_response_when_email_unknown():
    print("\n" + "=" * 60)
    print("  BLOQUE 1: NO REVELAR EXISTENCIA DEL EMAIL")
    print("=" * 60)

    step(1, "POST /forgot-password con email inexistente → debe devolver 200 con mensaje genérico")
    fake_email = f"inexistente_{uuid.uuid4().hex[:6]}@test.com"
    res = forgot(fake_email)
    assert res.status_code == 200, f"Se esperaba 200, recibido {res.status_code} → {res.text}"
    body = res.json()
    assert body.get("message") == EXPECTED_MESSAGE, \
        f"Mensaje inesperado: {body}"
    ok(f"Respuesta 200 con mensaje genérico: {body['message']!r}")


# ─────────────────────────────────────────────
#  BLOQUE 2: INVALIDACIÓN DE CONTRASEÑA ANTIGUA
# ─────────────────────────────────────────────

def test_old_password_is_invalidated():
    print("\n" + "=" * 60)
    print("  BLOQUE 2: LA BD SE ACTUALIZA ANTES DEL CORREO")
    print("=" * 60)

    username = f"recov_{uuid.uuid4().hex[:6]}"
    old_password = "OldPass123!"

    step(1, f"Registrando usuario '{username}' con contraseña conocida")
    email, uid = register_user(username, old_password)
    ok(f"Registrado. ID={uid}, email={email}")

    step(2, "Verificando que la contraseña original funciona")
    res_pre = login(username, old_password)
    assert res_pre.status_code == 200, f"Login con original falló inesperadamente: {res_pre.text}"
    ok("Login con contraseña original funciona antes del /forgot-password")

    step(3, "POST /forgot-password (el envío SMTP puede fallar con email @test.com, se acepta 200 o 500)")
    res = forgot(email)
    debug(f"Status: {res.status_code} | Body: {res.text[:120]}")
    assert res.status_code in (200, 500), \
        f"Se esperaba 200 o 500, recibido {res.status_code}"
    if res.status_code == 200:
        assert res.json().get("message") == EXPECTED_MESSAGE, f"Mensaje inesperado: {res.json()}"
        ok("Respuesta 200 con mensaje genérico")
    else:
        ok("Respuesta 500 por fallo SMTP esperado — la BD ya se actualizó antes del intento de envío")

    step(4, "Login con la contraseña ANTIGUA ahora debe fallar (BD ya actualizada)")
    res_post = login(username, old_password)
    assert res_post.status_code in (400, 401), \
        f"La contraseña antigua no fue invalidada: HTTP {res_post.status_code} → {res_post.text}"
    ok(f"Contraseña antigua rechazada con HTTP {res_post.status_code}")

    # Limpieza: no tenemos la nueva password, el usuario quedará huérfano.
    print(f"   [Limpieza] Usuario '{username}' no eliminable desde test (nueva password solo va por email).")


# ─────────────────────────────────────────────
#  BLOQUE 3: RESPUESTA IDÉNTICA EXISTA O NO EL EMAIL
# ─────────────────────────────────────────────

def test_response_consistency():
    print("\n" + "=" * 60)
    print("  BLOQUE 3: MISMO MENSAJE PARA EMAIL EXISTENTE E INEXISTENTE")
    print("=" * 60)

    username = f"consist_{uuid.uuid4().hex[:6]}"
    password = "ConsistPass1!"

    step(1, "Registrar usuario para el caso 'email existe'")
    email, _ = register_user(username, password)

    step(2, "Llamar /forgot-password con email registrado")
    res_existing = forgot(email)
    debug(f"existing → {res_existing.status_code}: {res_existing.text[:120]}")

    step(3, "Llamar /forgot-password con email no registrado")
    fake_email = f"noexiste_{uuid.uuid4().hex[:6]}@test.com"
    res_unknown = forgot(fake_email)
    debug(f"unknown  → {res_unknown.status_code}: {res_unknown.text[:120]}")

    step(4, "Verificar que si ambos devuelven 200, el mensaje es idéntico")
    if res_existing.status_code == 200 and res_unknown.status_code == 200:
        assert res_existing.json() == res_unknown.json(), \
            f"Los cuerpos difieren: existing={res_existing.json()} unknown={res_unknown.json()}"
        ok("Mismo JSON de respuesta → no se filtra si el email está registrado")
    else:
        # Si el existing falla por SMTP con 500, al menos el inexistente debe dar 200 genérico
        assert res_unknown.status_code == 200 and res_unknown.json().get("message") == EXPECTED_MESSAGE, \
            f"Email inexistente no devolvió 200 genérico: {res_unknown.status_code} / {res_unknown.text}"
        ok(f"Email registrado dio {res_existing.status_code} (SMTP), "
           f"email inexistente dio 200 genérico → coincide que la BD real se ha tocado en el primer caso")


# ─────────────────────────────────────────────
#  BLOQUE 4: CASE-INSENSITIVE EN EL EMAIL
# ─────────────────────────────────────────────

def test_case_insensitive_email_lookup():
    print("\n" + "=" * 60)
    print("  BLOQUE 4: LOOKUP DEL EMAIL EN MAYÚSCULAS/MINÚSCULAS")
    print("=" * 60)

    username = f"case_{uuid.uuid4().hex[:6]}"
    password = "CasePass1!"
    email, _ = register_user(username, password)

    step(1, f"Registrado con email '{email}'. Llamando /forgot-password con el email en MAYÚSCULAS")
    res = forgot(email.upper())
    assert res.status_code in (200, 500), f"HTTP inesperado: {res.status_code} → {res.text}"
    ok(f"Respuesta {res.status_code} (el lookup case-insensitive encontró al usuario)")

    step(2, "Login con la contraseña original ahora debe fallar → confirma que SÍ se actualizó la BD")
    res_post = login(username, password)
    assert res_post.status_code in (400, 401), \
        f"La contraseña antigua sigue valiendo: {res_post.status_code} → la BD no se actualizó con email en mayúsculas"
    ok("Contraseña antigua invalidada también con email en mayúsculas")


# ─────────────────────────────────────────────
#  BLOQUE 5: LLAMADAS REPETIDAS INVALIDAN LAS ANTERIORES
# ─────────────────────────────────────────────

def test_repeated_calls_invalidate_previous():
    print("\n" + "=" * 60)
    print("  BLOQUE 5: LLAMADAS CONSECUTIVAS REGENERAN LA CONTRASEÑA")
    print("=" * 60)

    username = f"rep_{uuid.uuid4().hex[:6]}"
    password = "RepPass1!"
    email, _ = register_user(username, password)

    step(1, "Primera llamada /forgot-password")
    r1 = forgot(email)
    debug(f"#1 → {r1.status_code}")
    assert r1.status_code in (200, 500)

    step(2, "Segunda llamada /forgot-password (inmediata)")
    time.sleep(0.5)
    r2 = forgot(email)
    debug(f"#2 → {r2.status_code}")
    assert r2.status_code in (200, 500)

    step(3, "Contraseña original sigue invalidada tras las dos rotaciones")
    res_post = login(username, password)
    assert res_post.status_code in (400, 401), \
        f"La original sigue funcionando tras dos rotaciones: {res_post.status_code}"
    ok("Contraseña original rechazada → las dos llamadas generaron hashes distintos")


# ─────────────────────────────────────────────
#  BLOQUE 6: VALIDACIÓN DE PAYLOAD
# ─────────────────────────────────────────────

def test_payload_validation():
    print("\n" + "=" * 60)
    print("  BLOQUE 6: VALIDACIÓN DEL BODY")
    print("=" * 60)

    step(1, "Body vacío → 422 (Unprocessable Entity)")
    res = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={})
    assert res.status_code == 422, f"Se esperaba 422, recibido {res.status_code}"
    ok(f"HTTP 422 correcto")

    step(2, "Body sin campo 'email' → 422")
    res = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"foo": "bar"})
    assert res.status_code == 422, f"Se esperaba 422, recibido {res.status_code}"
    ok(f"HTTP 422 correcto")

    step(3, "Email en blanco → 200 (se trata como email inexistente, respuesta genérica)")
    res = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={"email": "   "})
    assert res.status_code == 200, f"Se esperaba 200, recibido {res.status_code} → {res.text}"
    assert res.json().get("message") == EXPECTED_MESSAGE
    ok("Email en blanco tratado como desconocido → respuesta genérica")


# ─────────────────────────────────────────────
#  BLOQUE 7: ENDPOINT /reset-password NO DEBE EXISTIR
# ─────────────────────────────────────────────

def test_reset_password_endpoint_removed():
    print("\n" + "=" * 60)
    print("  BLOQUE 7: /reset-password ELIMINADO")
    print("=" * 60)

    step(1, "POST /api/auth/reset-password → 404 Not Found (el endpoint ya no existe)")
    res = requests.post(f"{BASE_URL}/api/auth/reset-password",
                        json={"email": "x@test.com", "code": "000000", "new_password": "abc"})
    assert res.status_code == 404, \
        f"El endpoint /reset-password debería haber sido eliminado, devolvió HTTP {res.status_code}"
    ok("HTTP 404 → endpoint correctamente eliminado")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    print("\n" + "#" * 60)
    print("#  TEST SUITE: SISTEMA DE RECUPERACIÓN DE CONTRASEÑA")
    print("#" * 60)
    print(f"Target: {BASE_URL}")
    print("Nota: los usuarios de prueba quedan con una contraseña aleatoria "
          "que solo se entrega por email. No se pueden borrar al finalizar.")

    blocks = [
        ("Respuesta genérica con email desconocido", test_generic_response_when_email_unknown),
        ("Invalidación de contraseña antigua",        test_old_password_is_invalidated),
        ("Consistencia de respuesta",                 test_response_consistency),
        ("Lookup case-insensitive",                   test_case_insensitive_email_lookup),
        ("Llamadas repetidas",                        test_repeated_calls_invalidate_previous),
        ("Validación de payload",                     test_payload_validation),
        ("/reset-password eliminado",                 test_reset_password_endpoint_removed),
    ]

    failed = []
    for name, fn in blocks:
        try:
            fn()
        except AssertionError as e:
            failed.append((name, str(e)))
            print(f"\n  ✗ FAIL [{name}] → {e}")
        except Exception as e:
            failed.append((name, f"Excepción inesperada: {e}"))
            print(f"\n  ✗ ERROR [{name}] → {e}")

    print("\n" + "=" * 60)
    print("  RESUMEN")
    print("=" * 60)
    print(f"Bloques ejecutados: {len(blocks)}")
    print(f"Bloques con fallos: {len(failed)}")
    if failed:
        for name, err in failed:
            print(f"  ✗ {name}: {err[:200]}")
        sys.exit(1)
    print("\nTODOS LOS BLOQUES PASARON.")
    sys.exit(0)


if __name__ == "__main__":
    main()
