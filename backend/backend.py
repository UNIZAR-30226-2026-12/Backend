import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback

# --- Imports de Dominio (Ordenados Alfabéticamente) ---
from auth.routes import router as auth_router
from avatar.routes import router as avatar_router
from friends.routes import router as friends_router
from lobby.routes import router as lobby_router
from persistence.database import database
from persistence.migrations import run_migrations
from ranking.routes import router as ranking_router
from users.routes import router as users_router
from ws.routes import router as ws_router

"""
Endpoints del Backend ---> mirar en APIDOCS.md
"""

app = FastAPI(title="Reversi AI Backend")

# --- Manejo Global de Excepciones ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"CRITICAL ERROR AVOIDED: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Ha ocurrido un error interno en el servidor. Inténtalo más tarde."},
    )

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
app.include_router(ranking_router, prefix="/api/ranking", tags=["Ranking"]) 
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(ws_router, prefix="/ws", tags=["WebSockets"])

# --- Eventos de Base de Datos ---
@app.on_event("startup")
async def startup():
    await database.connect()
    await run_migrations()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()