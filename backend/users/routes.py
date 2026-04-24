from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from collections import Counter
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


def _normalize_mode(mode: str) -> str:
    normalized = (mode or "").strip().lower()
    if normalized in {"1vs1", "1v1"}:
        return "1vs1"
    if normalized in {"1vs1vs1vs1", "1v1v1v1"}:
        return "1vs1vs1vs1"
    return normalized


def _normalize_result(result: str) -> str:
    return (result or "").replace("Ã‚Âº", "º").replace("Âº", "º").strip()


def _placement_from_result(result: str):
    normalized = _normalize_result(result)
    if normalized and normalized[0].isdigit():
        return int(normalized[0])
    return None

def _split_opponents(opponent_name: str) -> List[str]:
    if not opponent_name:
        return []
    if opponent_name == "N/A":
        return []
    return [name.strip() for name in opponent_name.split(",") if name and name.strip()]


def _top_counter_entry(counter: Counter):
    if not counter:
        return None, 0
    name, value = counter.most_common(1)[0]
    return name, value


def _build_1v1_stats(rows: List[dict], elo: int, peak_elo: int) -> dict:
    one_vs_one_rows = [row for row in rows if _normalize_mode(row["mode"]) == "1vs1"]
    one_vs_one_rows.sort(key=lambda row: row["created_at"])

    total = len(one_vs_one_rows)
    wins = sum(1 for row in one_vs_one_rows if _normalize_result(row["result"]) == "Ganada")
    losses = sum(1 for row in one_vs_one_rows if _normalize_result(row["result"]) == "Perdida")
    draws = sum(1 for row in one_vs_one_rows if _normalize_result(row["result"]) == "Empate")
    winrate = round((wins / total) * 100, 1) if total > 0 else 0.0

    win_streak = 0
    current_streak = 0
    for row in one_vs_one_rows:
        if _normalize_result(row["result"]) == "Ganada":
            current_streak += 1
            win_streak = max(win_streak, current_streak)
        else:
            current_streak = 0

    black_total = sum(1 for row in one_vs_one_rows if (row["player_color"] or "").lower() == "black")
    black_wins = sum(
        1
        for row in one_vs_one_rows
        if (row["player_color"] or "").lower() == "black" and _normalize_result(row["result"]) == "Ganada"
    )
    white_total = sum(1 for row in one_vs_one_rows if (row["player_color"] or "").lower() == "white")
    white_wins = sum(
        1
        for row in one_vs_one_rows
        if (row["player_color"] or "").lower() == "white" and _normalize_result(row["result"]) == "Ganada"
    )

    winrate_black = round((black_wins / black_total) * 100, 1) if black_total > 0 else 0.0
    winrate_white = round((white_wins / white_total) * 100, 1) if white_total > 0 else 0.0

    nemesis_counter = Counter(
        row["opponent_name"]
        for row in one_vs_one_rows
        if _normalize_result(row["result"]) == "Perdida" and row["opponent_name"]
    )
    victim_counter = Counter(
        row["opponent_name"]
        for row in one_vs_one_rows
        if _normalize_result(row["result"]) == "Ganada" and row["opponent_name"]
    )
    nemesis_name, nemesis_losses = _top_counter_entry(nemesis_counter)
    victim_name, victim_wins = _top_counter_entry(victim_counter)

    return {
        "elo": elo,
        "peak_elo": peak_elo,
        "total_games": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "winrate": winrate,
        "win_streak": win_streak,
        "winrate_black": winrate_black,
        "winrate_white": winrate_white,
        "nemesis_name": nemesis_name,
        "nemesis_losses": nemesis_losses,
        "victim_name": victim_name,
        "victim_wins": victim_wins,
    }


def _build_4p_stats(rows: List[dict], elo: int, peak_elo: int) -> dict:
    four_player_rows = [row for row in rows if _normalize_mode(row["mode"]) == "1vs1vs1vs1"]
    four_player_rows.sort(key=lambda row: row["created_at"])

    rows_with_placement = [
        (row, _placement_from_result(row["result"]))
        for row in four_player_rows
    ]
    valid_rows = [(row, placement) for row, placement in rows_with_placement if placement in {1, 2, 3, 4}]

    total = len(valid_rows)
    first_place = sum(1 for _, placement in valid_rows if placement == 1)
    second_place = sum(1 for _, placement in valid_rows if placement == 2)
    third_place = sum(1 for _, placement in valid_rows if placement == 3)
    fourth_place = sum(1 for _, placement in valid_rows if placement == 4)

    wins = first_place
    losses = max(0, total - first_place)
    winrate = round((wins / total) * 100, 1) if total > 0 else 0.0

    win_streak = 0
    current_streak = 0
    for _, placement in valid_rows:
        if placement == 1:
            current_streak += 1
            win_streak = max(win_streak, current_streak)
        else:
            current_streak = 0

    nemesis_counter: Counter = Counter()
    victim_counter: Counter = Counter()
    for row, placement in valid_rows:
        opponents = _split_opponents(row["opponent_name"] or "")
        if placement == 1:
            for opponent in opponents:
                victim_counter[opponent] += 1
        else:
            for opponent in opponents:
                nemesis_counter[opponent] += 1

    nemesis_name, nemesis_losses = _top_counter_entry(nemesis_counter)
    victim_name, victim_wins = _top_counter_entry(victim_counter)

    return {
        "elo": elo,
        "peak_elo": peak_elo,
        "total_games": total,
        "wins": wins,
        "losses": losses,
        "draws": 0,
        "winrate": winrate,
        "win_streak": win_streak,
        "first_place": first_place,
        "second_place": second_place,
        "third_place": third_place,
        "fourth_place": fourth_place,
        "nemesis_name": nemesis_name,
        "nemesis_losses": nemesis_losses,
        "victim_name": victim_name,
        "victim_wins": victim_wins,
    }


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
    query = "SELECT elo, username, peak_elo, avatar_url FROM users WHERE id = :user_id"
    user = await database.fetch_one(query=query, values={"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    query_history = """
        SELECT mode, result, opponent_name, player_color, created_at
        FROM game_history
        WHERE user_id = :user_id
        ORDER BY created_at ASC
    """
    rows = await database.fetch_all(query=query_history, values={"user_id": user_id})

    peak_elo = user["peak_elo"] if user["peak_elo"] is not None else user["elo"]
    stats_1v1 = _build_1v1_stats(rows, user["elo"], peak_elo)
    stats_4p = _build_4p_stats(rows, user["elo"], peak_elo)

    return {
        "username": user["username"],
        "elo": user["elo"],
        "avatar_url": user["avatar_url"],
        "total_games": stats_1v1["total_games"],
        "wins": stats_1v1["wins"],
        "losses": stats_1v1["losses"],
        "draws": stats_1v1["draws"],
        "winrate": stats_1v1["winrate"],
        "peak_elo": peak_elo,
        "win_streak": stats_1v1["win_streak"],
        "winrate_black": stats_1v1["winrate_black"],
        "winrate_white": stats_1v1["winrate_white"],
        "nemesis_name": stats_1v1["nemesis_name"],
        "nemesis_losses": stats_1v1["nemesis_losses"],
        "victim_name": stats_1v1["victim_name"],
        "victim_wins": stats_1v1["victim_wins"],
        "stats_1v1": stats_1v1,
        "stats_4p": stats_4p,
    }


@router.get("/{user_id}/h2h")
async def read_h2h(user_id: int, current_user: dict = Depends(get_current_user)):
    query_friend = "SELECT username FROM users WHERE id = :user_id"
    friend = await database.fetch_one(query=query_friend, values={"user_id": user_id})
    if not friend:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    friend_name = friend["username"]

    # strpos() busca el nombre del rival dentro del campo opponent_name.
    # Paddeamos con ', ' para evitar coincidencias parciales (ej: "Al" dentro de "Alice").
    query_h2h = """
        SELECT mode, result, opponent_name
        FROM game_history
        WHERE user_id = :uid
          AND strpos(', ' || opponent_name || ', ', ', ' || :friend_name || ', ') > 0
    """
    rows = await database.fetch_all(
        query=query_h2h,
        values={"uid": current_user["id"], "friend_name": friend_name},
    )

    total_matches = 0
    wins = 0
    losses = 0
    draws = 0

    total_matches_4p = 0
    first_places_4p = 0
    other_places_4p = 0

    for row in rows:
        mode = _normalize_mode(row["mode"])
        opponent_name = (row["opponent_name"] or "").strip()

        if mode == "1vs1":
            if opponent_name != friend_name:
                continue
            total_matches += 1
            result = _normalize_result(row["result"])
            if result == "Ganada":
                wins += 1
            elif result == "Perdida":
                losses += 1
            elif result == "Empate":
                draws += 1
            continue

        if mode == "1vs1vs1vs1":
            opponents = _split_opponents(opponent_name)
            if friend_name not in opponents:
                continue
            placement = _placement_from_result(row["result"])
            if placement == 1:
                total_matches_4p += 1
                first_places_4p += 1
            elif placement in {2, 3, 4}:
                total_matches_4p += 1
                other_places_4p += 1

    return {
        "total_matches": total_matches,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "total_matches_4p": total_matches_4p,
        "first_places_4p": first_places_4p,
        "other_places_4p": other_places_4p,
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
            raise HTTPException(status_code=400, detail="El nombre de usuario no puede estar vacÃ­o")

        query_check = "SELECT id FROM users WHERE username = :un AND id != :uid"
        existing = await database.fetch_one(query=query_check, values={"un": normalized_username, "uid": current_user["id"]})
        if existing:
            raise HTTPException(status_code=400, detail="Este nombre de usuario ya estÃ¡ registrado")
        username = normalized_username

    if update.email is not None:
        normalized_email = update.email.strip()
        if not normalized_email:
            raise HTTPException(status_code=400, detail="El correo electrÃ³nico no puede estar vacÃ­o")
        query_check = "SELECT id FROM users WHERE email = :em AND id != :uid"
        existing = await database.fetch_one(query=query_check, values={"em": normalized_email, "uid": current_user["id"]})
        if existing:
            raise HTTPException(status_code=400, detail="Este correo electrÃ³nico ya estÃ¡ registrado")
        email = normalized_email

    if new_password is not None:
        if not update.current_password:
            raise HTTPException(status_code=400, detail="Debes indicar la contraseÃ±a actual para cambiarla")
        if not verify_password(update.current_password, current_user["password_hash"]):
            raise HTTPException(status_code=400, detail="La contraseÃ±a actual no es correcta")

        cleaned_new_password = new_password.strip()
        if len(cleaned_new_password) < 6:
            raise HTTPException(status_code=400, detail="La nueva contraseÃ±a debe tener al menos 6 caracteres")

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
async def get_my_history(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100),
    mode: str | None = Query(default=None),
):
    return await get_user_history_data(current_user["id"], limit=limit, mode=mode)


@router.get("/{user_id}/history", response_model=List[GameHistoryResponse])
async def get_user_history(
    user_id: int,
    limit: int = Query(10, ge=1, le=100),
    mode: str | None = Query(default=None),
):
    return await get_user_history_data(user_id, limit=limit, mode=mode)


async def get_user_history_data(user_id: int, limit: int = 10, mode: str | None = None):
    query = """
        SELECT id, created_at, mode, result, score, rank_change, opponent_name, player_color
        FROM game_history
        WHERE user_id = :uid
    """
    values = {"uid": user_id, "limit": limit}

    if mode:
        normalized_mode = _normalize_mode(mode)
        if normalized_mode == "1vs1":
            query += " AND mode IN ('1vs1', '1v1', '1vs1_skills', '1v1_skills')"
        elif normalized_mode == "1vs1vs1vs1":
            query += " AND mode IN ('1vs1vs1vs1', '1v1v1v1', '1vs1vs1vs1_skills', '1v1v1v1_skills')"
        elif normalized_mode:
            query += " AND mode = :mode"
            values["mode"] = normalized_mode

    query += " ORDER BY created_at DESC LIMIT :limit"

    rows = await database.fetch_all(query=query, values=values)

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

    # 4. Borramos su historial estadÃ­stico
    await database.execute(
        "DELETE FROM game_history WHERE user_id = :uid",
        {"uid": user_id},
    )

    # 5. Borramos al usuario (los lobbies se borran en cascada automáticamente)
    # El avatar se borra automáticamente al eliminar la fila (está guardado en avatar_url como base64)
    await database.execute(
        "DELETE FROM users WHERE id = :uid",
        {"uid": user_id},
    )

    return {"status": "success", "message": f"Usuario {username} y todos sus datos han sido eliminados"}




