from fastapi import APIRouter
from .registry import SKILLS_LIST

router = APIRouter()

@router.get("/")
async def get_all_skills():
    """Retorna la lista oficial de habilidades."""
    return {"skills": SKILLS_LIST}
