from fastapi import APIRouter, HTTPException, Depends
from typing import List
from persistence.database import database
from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from auth.security import get_password_hash, verify_password
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


@router.get("/me/stats")
async def read_my_stats(current_user: dict = Depends(get_current_user)):
    return await get_user_statistics(current_user["id"])


@router.get("/{user_id}/stats")
async def read_user_stats(user_id: int):
    return await get_user_statistics(user_id)


async def get_user_statistics(user_id: int):
    query = "SELECT elo, username, peak_elo FROM users WHERE id = :user_id"
    user = await database.fetch_one(query=query, values={"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Estadísticas básicas
    query_games = """
        SELECT COUNT(*) as total,
               SUM(CASE WHEN result = 'Ganada' THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN result = 'Perdida' THEN 1 ELSE 0 END) as losses,
               SUM(CASE WHEN result = 'Empate' THEN 1 ELSE 0 END) as draws
        FROM game_history
        WHERE user_id = :user_id
    """
    stats = await database.fetch_one(query=query_games, values={"user_id": user_id})

    total = stats["total"] or 0
    wins = stats["wins"] or 0
    losses = stats["losses"] or 0
    draws = stats["draws"] or 0
    winrate = round((wins / total) * 100, 1) if total > 0 else 0.0

    # Mejor racha de victorias consecutivas
    query_results = """
        SELECT result FROM game_history
        WHERE user_id = :user_id
        ORDER BY created_at ASC
    """
    rows = await database.fetch_all(query=query_results, values={"user_id": user_id})
    win_streak = 0
    current_streak = 0
    for row in rows:
        if row["result"] == "Ganada":
            current_streak += 1
            win_streak = max(win_streak, current_streak)
        else:
            current_streak = 0

    # Winrate por color de ficha
    query_color = """
        SELECT player_color,
               COUNT(*) as total,
               SUM(CASE WHEN result = 'Ganada' THEN 1 ELSE 0 END) as wins
        FROM game_history
        WHERE user_id = :user_id
        GROUP BY player_color
    """
    color_rows = await database.fetch_all(query=query_color, values={"user_id": user_id})
    winrate_black = 0.0
    winrate_white = 0.0
    for cr in color_rows:
        if cr["total"] > 0:
            wr = round((cr["wins"] / cr["total"]) * 100, 1)
            if cr["player_color"] == "black":
                winrate_black = wr
            elif cr["player_color"] == "white":
                winrate_white = wr

    # Némesis: rival que más veces nos ha ganado
    query_nemesis = """
        SELECT opponent_name, COUNT(*) as cnt
        FROM game_history
        WHERE user_id = :user_id AND result = 'Perdida'
        GROUP BY opponent_name
        ORDER BY cnt DESC
        LIMIT 1
    """
    nemesis_row = await database.fetch_one(query=query_nemesis, values={"user_id": user_id})
    nemesis_name = nemesis_row["opponent_name"] if nemesis_row and nemesis_row["cnt"] > 0 else None
    nemesis_losses = nemesis_row["cnt"] if nemesis_row else 0

    # Víctima: rival al que más veces hemos ganado
    query_victim = """
        SELECT opponent_name, COUNT(*) as cnt
        FROM game_history
        WHERE user_id = :user_id AND result = 'Ganada'
        GROUP BY opponent_name
        ORDER BY cnt DESC
        LIMIT 1
    """
    victim_row = await database.fetch_one(query=query_victim, values={"user_id": user_id})
    victim_name = victim_row["opponent_name"] if victim_row and victim_row["cnt"] > 0 else None
    victim_wins = victim_row["cnt"] if victim_row else 0

    # Pico de RR
    peak_elo = user["peak_elo"] if user["peak_elo"] is not None else user["elo"]

    return {
        "username": user["username"],
        "elo": user["elo"],
        "total_games": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "winrate": winrate,
        "peak_elo": peak_elo,
        "win_streak": win_streak,
        "winrate_black": winrate_black,
        "winrate_white": winrate_white,
        "nemesis_name": nemesis_name,
        "nemesis_losses": nemesis_losses,
        "victim_name": victim_name,
        "victim_wins": victim_wins,
    }


@router.get("/{user_id}/h2h")
async def read_h2h(user_id: int, current_user: dict = Depends(get_current_user)):
    query_friend = "SELECT username FROM users WHERE id = :user_id"
    friend = await database.fetch_one(query=query_friend, values={"user_id": user_id})
    if not friend:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    friend_name = friend["username"]

    query_h2h = """
        SELECT 
            COUNT(*) as total_matches,
            SUM(CASE WHEN result = 'Ganada' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'Perdida' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'Empate' THEN 1 ELSE 0 END) as draws
        FROM game_history
        WHERE user_id = :uid AND opponent_name = :opp_name
    """
    stats = await database.fetch_one(query=query_h2h, values={"uid": current_user["id"], "opp_name": friend_name})

    return {
        "total_matches": stats["total_matches"] if stats and stats["total_matches"] else 0,
        "wins": stats["wins"] if stats and stats["wins"] else 0,
        "losses": stats["losses"] if stats and stats["losses"] else 0,
        "draws": stats["draws"] if stats and stats["draws"] else 0,
    }


@router.put("/me", response_model=UserResponse)
async def update_user_me(update: UserUpdate, current_user: dict = Depends(get_current_user)):
    username = current_user["username"]
    email = current_user["email"]
    new_password = update.new_password or update.password
    new_password_hash = None

    if update.username is not None:
        normalized_username = update.username.strip()
        if not normalized_username:
            raise HTTPException(status_code=400, detail="El nombre de usuario no puede estar vacío")

        query_check = "SELECT id FROM users WHERE username = :un AND id != :uid"
        existing = await database.fetch_one(query=query_check, values={"un": normalized_username, "uid": current_user["id"]})
        if existing:
            raise HTTPException(status_code=400, detail="Este nombre de usuario ya está registrado")
        username = normalized_username

    if update.email is not None:
        normalized_email = update.email.strip()
        if not normalized_email:
            raise HTTPException(status_code=400, detail="El correo electrónico no puede estar vacío")
        query_check = "SELECT id FROM users WHERE email = :em AND id != :uid"
        existing = await database.fetch_one(query=query_check, values={"em": normalized_email, "uid": current_user["id"]})
        if existing:
            raise HTTPException(status_code=400, detail="Este correo electrónico ya está registrado")
        email = normalized_email

    if new_password is not None:
        if not update.current_password:
            raise HTTPException(status_code=400, detail="Debes indicar la contraseña actual para cambiarla")
        if not verify_password(update.current_password, current_user["password_hash"]):
            raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")

        cleaned_new_password = new_password.strip()
        if len(cleaned_new_password) < 6:
            raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres")

        new_password_hash = get_password_hash(cleaned_new_password)

    if new_password_hash is not None:
        query = """
            UPDATE users
            SET username = :un, email = :em, password_hash = :pw
            WHERE id = :uid
        """
        await database.execute(
            query=query,
            values={"un": username, "em": email, "pw": new_password_hash, "uid": current_user["id"]},
        )
    else:
        query = "UPDATE users SET username = :un, email = :em WHERE id = :uid"
        await database.execute(query=query, values={"un": username, "em": email, "uid": current_user["id"]})

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
    query = """
        UPDATE users
        SET elo = :elo,
            peak_elo = GREATEST(COALESCE(peak_elo, elo), :elo)
        WHERE id = :uid
    """
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
        INSERT INTO game_history (user_id, opponent_name, mode, result, score, rank_change, player_color)
        VALUES (:user_id, :opponent_name, :mode, :result, :score, :rank_change, :player_color)
        RETURNING id, created_at, mode, result, score, rank_change, player_color
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
            "player_color": entry.player_color or "black",
        },
    )

    return GameHistoryResponse(
        id=row["id"],
        date=row["created_at"].strftime("%Y-%m-%d"),
        mode=row["mode"],
        result=row["result"],
        score=row["score"],
        rankChange=row["rank_change"],
        player_color=row["player_color"],
    )


@router.get("/me/history", response_model=List[GameHistoryResponse])
async def get_my_history(current_user: dict = Depends(get_current_user)):
    return await get_user_history_data(current_user["id"])


@router.get("/{user_id}/history", response_model=List[GameHistoryResponse])
async def get_user_history(user_id: int):
    return await get_user_history_data(user_id)


async def get_user_history_data(user_id: int):
    query = """
        SELECT id, created_at, mode, result, score, rank_change, opponent_name, player_color
        FROM game_history
        WHERE user_id = :uid
        ORDER BY created_at DESC
        LIMIT 10
    """
    rows = await database.fetch_all(query=query, values={"uid": user_id})

    history = []
    for row in rows:
        history.append(GameHistoryResponse(
            id=row["id"],
            date=row["created_at"].strftime("%Y-%m-%d"),
            opponent_name=row["opponent_name"],
            mode=row["mode"],
            result=row["result"],
            score=row["score"],
            rankChange=row["rank_change"],
            player_color=row["player_color"],
        ))
    return history


@router.delete("/me")
async def delete_my_account(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    username = current_user["username"]

    # 1. Borramos relaciones sociales (amistades y rechazos)
    await database.execute(
        "DELETE FROM friendships WHERE user_id = :uid OR friend_id = :uid",
        {"uid": user_id},
    )
    await database.execute(
        "DELETE FROM friend_request_rejections WHERE sender_id = :uid OR receiver_id = :uid",
        {"uid": user_id},
    )

    # 2. Borramos movimientos hechos por el jugador
    await database.execute(
        "DELETE FROM moves WHERE player_id = :uid",
        {"uid": user_id},
    )

    # 3. Borramos las partidas en las que ha participado
    await database.execute(
        "DELETE FROM games WHERE player1_id = :uid OR player2_id = :uid OR player3_id = :uid OR player4_id = :uid",
        {"uid": user_id},
    )

    # 4. Borramos su historial estadístico
    await database.execute(
        "DELETE FROM game_history WHERE user_id = :uid",
        {"uid": user_id},
    )

    # 5. Finalmente, borramos al usuario (los lobbies se borran en cascada automáticamente)
    await database.execute(
        "DELETE FROM users WHERE id = :uid",
        {"uid": user_id},
    )

    return {"status": "success", "message": f"Usuario {username} y todos sus datos han sido eliminados"}
