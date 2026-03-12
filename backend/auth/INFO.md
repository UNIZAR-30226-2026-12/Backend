# Módulo: Auth (Autenticación)

**Responsabilidad:**
Gestión de la seguridad, registro, e inicio de sesión. Contiene la lógica para generar y validar tokens JWT y el hashing de contraseñas usando `passlib/bcrypt`.

**Archivos previstos:**
- `services.py`: Lógica para `verify_password`, `get_password_hash`, y `create_access_token`.
- `dependencies.py`: Función `get_current_user` para proteger rutas.