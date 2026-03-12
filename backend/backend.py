import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- Imports de Dominio (Ordenados Alfabéticamente) ---
from auth.routes import router as auth_router
from avatar.routes import router as avatar_router
from friends.routes import router as friends_router
from lobby.routes import router as lobby_router
from persistence.database import database
from users.routes import router as users_router
from ws.routes import router as ws_router

"""
Endpoints del Backend:
- POST /api/auth/register : Registro de nuevos usuarios
- POST /api/auth/login : Inicio de sesión (OAuth2)
- GET  /api/users/me : Obtener datos del perfil actual
- GET  /api/users/{user_id}/stats : Obtener estadísticas de un usuario
- PUT  /api/users/me : Actualizar información básica (username, email)
- PUT  /api/users/customization : Actualizar preferencias estéticas
- POST /api/users/avatar : Subida de imagen de avatar
- GET  /api/users/me/history : Historial de partidas del usuario
- GET  /api/friends : Listar amigos, solicitudes e invitaciones a juegos
- POST /api/friends/request : Enviar solicitud de amistad
- POST /api/friends/{user_id}/accept : Aceptar solicitud de amistad
- POST /api/friends/{user_id}/reject : Rechazar solicitud o eliminar amigo
- DELETE /api/friends/{user_id} : Eliminar amigo (alias de reject)
- POST /api/games/invite : Invitar a un amigo a una partida privada
- POST /partida : (Legacy) Crear partida rápida
- POST /movimiento : (Legacy) Realizar movimiento en partida
"""

app = FastAPI(title="Reversi AI Backend")

# --- Configuracion de Archivos Estáticos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
AVATARS_UPLOADS_DIR = os.path.join(UPLOADS_DIR, "avatars")
os.makedirs(AVATARS_UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# --- Habilitar CORS para permitir peticiones desde el frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Registro de Routers ---
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(avatar_router, prefix="/api/users", tags=["Avatar"])
app.include_router(friends_router, prefix="/api/friends", tags=["Friends"])
app.include_router(lobby_router, prefix="/api/games", tags=["Games/Lobby"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(ws_router, prefix="/ws", tags=["WebSockets"])

# --- Eventos de Base de Datos ---
@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()