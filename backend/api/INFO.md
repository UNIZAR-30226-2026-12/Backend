# Módulo: API (Controladores)

**Responsabilidad:** Capa de entrada HTTP del sistema. Aquí se definen los routers de FastAPI que exponen los endpoints REST (versión 1). No debe contener lógica de negocio, sino que recibe la petición, valida los datos de entrada con Pydantic y delega la ejecución al módulo de dominio correspondiente.

**Ejemplo de uso previsto:**
Un archivo `api/routes.py` que agrupa todos los routers:
`app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])`