from fastapi import APIRouter
from persistence.database import database

router = APIRouter()

@router.get("/")
async def get_global_ranking():
    """
    Obtiene el Top 50 de jugadores globales ordenados por ELO (RR).
    Ideal para mostrar en la pantalla del Leaderboard.
    """
    query = """
        SELECT id, username, elo, avatar_url
        FROM users
        ORDER BY elo DESC
        LIMIT 50
    """
    rows = await database.fetch_all(query=query)
    
    # Convertimos los registros de la DB en una lista de diccionarios
    ranking = [dict(row) for row in rows]
    
    return {"ranking": ranking}