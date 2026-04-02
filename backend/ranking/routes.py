from fastapi import APIRouter, Query
from persistence.database import database

router = APIRouter()

@router.get("/")
async def get_global_ranking(limit: int = Query(50, ge=1, le=100), skip: int = Query(0, ge=0)):
    """
    Obtiene el Top de jugadores globales ordenados por ELO (RR).
    Incluye paginación. Ejemplo: /api/ranking/?limit=50&skip=0
    """
    query = """
        SELECT id, username, elo, avatar_url
        FROM users
        ORDER BY elo DESC
        LIMIT :limit OFFSET :skip
    """
    rows = await database.fetch_all(query=query, values={"limit": limit, "skip": skip})
    ranking = [dict(row) for row in rows]
    return {"ranking": ranking}