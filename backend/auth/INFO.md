# Módulo: Auth (Autenticación)

**Responsabilidad:**
Gestión de la seguridad, registro, inicio de sesión y recuperación de contraseña. Contiene la lógica para generar y validar tokens JWT, el hashing de contraseñas con `passlib/bcrypt` y el envío de correos SMTP para recuperación.

**Archivos:**
- `routes.py`: Endpoints `POST /register`, `POST /login`, `POST /forgot-password`.
- `schemas.py`: Pydantic models (`UserCreate`, `UserResponse`, `Token`, `ForgotPasswordRequest`).
- `security.py`: `verify_password`, `get_password_hash`, `create_access_token`.
- `dependencies.py`: `get_current_user` para proteger rutas.
- `email_service.py`: `send_new_password_email` — envío SMTP (Gmail) de la nueva contraseña en texto plano.

---

## Flujo de recuperación de contraseña (`POST /forgot-password`)

Flujo simplificado sin tokens ni segundo endpoint:

1. El cliente envía `{ email }`.
2. Se busca el usuario por email (case-insensitive).
3. **Si no existe** → se devuelve `200 OK` con el mismo mensaje genérico (no revelar si el email está registrado).
4. **Si existe:**
   a. Se genera una contraseña aleatoria de 8 caracteres (`secrets`), garantizando al menos 1 mayúscula, 1 minúscula y 1 dígito; el resto se toma del conjunto `a-z A-Z 0-9 !@#$%&*-_+=?`.
   b. Se hashea con `get_password_hash` (bcrypt).
   c. Se **actualiza el hash en la BD primero**.
   d. Se **envía el correo después** con la nueva contraseña en texto plano.
5. Se devuelve `200 OK` con `{ message: "Si el correo existe, recibirás una nueva contraseña" }`.

> El orden (BD antes que correo) evita dejar al usuario con credenciales contradictorias si falla el envío SMTP: la contraseña antigua queda siempre invalidada y un reintento regenera otra nueva.

### Variables de entorno SMTP

Leídas en `email_service.py`:

| Variable | Valor por defecto | Uso |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | Servidor SMTP |
| `SMTP_PORT` | `587` | Puerto (STARTTLS) |
| `SMTP_USER` | _(vacío)_ | Cuenta remitente |
| `SMTP_PASSWORD` | _(vacío)_ | App Password de Google |

Se definen en el servicio `backend` del `docker-compose.yml` del workspace.
