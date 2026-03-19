from fastapi import APIRouter, HTTPException, Depends
from typing import List
from persistence.database import database
from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from users.schemas import (
    UserUpdate,
    CustomizationUpdate,
    EloUpdate,
    GameHistoryCreate,
    GameHistoryResponse,
)

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.get("/{user_id}/stats")
async def read_user_stats(user_id: int):
    query = "SELECT elo, username FROM users WHERE id = :user_id"
    user = await database.fetch_one(query=query, values={"user_id": user_id})
    if not user:
         raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    query_games = "SELECT COUNT(*) as total, SUM(CASE WHEN winner_id = :user_id THEN 1 ELSE 0 END) as wins FROM games WHERE player1_id = :user_id OR player2_id = :user_id"
    stats = await database.fetch_one(query=query_games, values={"user_id": user_id})
    
    return {
        "username": user["username"],
        "elo": user["elo"],
        "total_games": stats["total"] if stats else 0,
        "wins": stats["wins"] if stats and stats["wins"] else 0
    }

@router.put("/me", response_model=UserResponse)
async def update_user_me(update: UserUpdate, current_user: dict = Depends(get_current_user)):
    values = {}
    if update.username is not None:
        normalized_username = update.username.strip()
        if not normalized_username:
            raise HTTPException(status_code=400, detail="El nombre de usuario no puede estar vacío")

        query_check = "SELECT id FROM users WHERE username = :un AND id != :uid"
        existing = await database.fetch_one(query=query_check, values={"un": normalized_username, "uid": current_user["id"]})
        if existing:
            raise HTTPException(status_code=400, detail="Este nombre de usuario ya está registrado")
        values["un"] = normalized_username
    else:
        values["un"] = current_user["username"]
    
    if update.email is not None:
        normalized_email = update.email.strip()
        if not normalized_email:
            raise HTTPException(status_code=400, detail="El correo electrónico no puede estar vacío")
        values["em"] = normalized_email
    else:
        values["em"] = current_user["email"]
    
    query = "UPDATE users SET username = :un, email = :em WHERE id = :uid"
    await database.execute(query=query, values={**values, "uid": current_user["id"]})
    
    updated_user = await database.fetch_one(query="SELECT * FROM users WHERE id = :uid", values={"uid": current_user["id"]})
    return dict(updated_user)

@router.put("/customization", response_model=UserResponse)
async def update_customization(update: CustomizationUpdate, current_user: dict = Depends(get_current_user)):
    updates = []
    values = {"uid": current_user["id"]}
    
    if update.avatar_url is not None:
        updates.append("avatar_url = :avatar")
        values["avatar"] = update.avatar_url
    if update.preferred_piece_color is not None:
        updates.append("preferred_piece_color = :piece")
        values["piece"] = update.preferred_piece_color
    if update.preferred_board_color is not None:
        updates.append("preferred_board_color = :board")
        values["board"] = update.preferred_board_color
        
    if not updates:
        return current_user
        
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = :uid"
    await database.execute(query=query, values=values)
    
    updated_user = await database.fetch_one(query="SELECT * FROM users WHERE id = :uid", values={"uid": current_user["id"]})
    return dict(updated_user)

@router.put("/me/elo", response_model=UserResponse)
async def update_my_elo(update: EloUpdate, current_user: dict = Depends(get_current_user)):
    query = "UPDATE users SET elo = :elo WHERE id = :uid"
    await database.execute(query=query, values={"elo": update.elo, "uid": current_user["id"]})

    updated_user = await database.fetch_one(
        query="SELECT * FROM users WHERE id = :uid",
        values={"uid": current_user["id"]},
    )
    return dict(updated_user)

@router.post("/me/history", response_model=GameHistoryResponse)
async def create_my_history_entry(
    entry: GameHistoryCreate,
    current_user: dict = Depends(get_current_user),
):
    query = """
        INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change)
        VALUES (:user_id, :opponent_name, :mode, :result, :score, :rank_change)
        RETURNING id, created_at, mode, result, score, rank_change
    """
    row = await database.fetch_one(
        query=query,
        values={
            "user_id": current_user["id"],
            "opponent_name": entry.opponent_name.strip(),
            "mode": entry.mode,
            "result": entry.result,
            "score": entry.score,
            "rank_change": entry.rankChange,
        },
    )

    return GameHistoryResponse(
        id=row["id"],
        date=row["created_at"].strftime("%Y-%m-%d"),
        mode=row["mode"],
        result=row["result"],
        score=row["score"],
        rankChange=row["rank_change"],
    )

@router.get("/me/history", response_model=List[GameHistoryResponse])
async def get_my_history(current_user: dict = Depends(get_current_user)):
    query = """
        SELECT id, created_at, mode, result, score, rank_change
        FROM game_history
        WHERE user_id = :uid
        ORDER BY created_at DESC
    """
    rows = await database.fetch_all(query=query, values={"uid": current_user["id"]})

    history = []
    for row in rows:
        history.append(GameHistoryResponse(
            id=row["id"],
            date=row["created_at"].strftime("%Y-%m-%d"),
            mode=row["mode"],
            result=row["result"],
            score=row["score"],
            rankChange=row["rank_change"],
        ))
    return history
