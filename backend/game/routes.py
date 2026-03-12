import uuid
from fastapi import APIRouter, HTTPException
from typing import Dict
from rules.schemas import Coordinate
from rules.logic import create_initial_board, is_valid_move, apply_move, get_valid_moves, count_score, resolve_game_state
from ai.engine import get_best_ai_move
from game.schemas import GameStateResponse, MoveRequest

router = APIRouter()

# --- DB en memoria ---
games_db: Dict[str, GameStateResponse] = {}

@router.post("/partida", response_model=GameStateResponse)
async def create_game():
    game_id = str(uuid.uuid4())
    board = create_initial_board()
    valid = get_valid_moves(board, 'black')
    state = GameStateResponse(
        game_id=game_id, 
        board=board, 
        current_player='black', 
        winner=None, 
        game_over=False, 
        score={"black": 2, "white": 2},
        valid_moves=valid
    )
    games_db[game_id] = state
    return state

@router.post("/movimiento", response_model=GameStateResponse)
async def make_move(move_req: MoveRequest):
    if move_req.game_id not in games_db: raise HTTPException(status_code=404, detail="Partida no encontrada")
    game = games_db[move_req.game_id]
    
    if game.game_over: raise HTTPException(status_code=400, detail="El juego ya terminó")
    if not is_valid_move(game.board, move_req.player, move_req.row, move_req.col):
        raise HTTPException(status_code=400, detail="Movimiento inválido")
    
    # 1. Aplicar movimiento humano
    game.board = apply_move(game.board, move_req.player, move_req.row, move_req.col)
    game.last_move = Coordinate(row=move_req.row, col=move_req.col)
    
    # 2. Determinar quién sigue (o si acabó)
    next_p = 'white' if move_req.player == 'black' else 'black'
    over, winner, current, valid = resolve_game_state(game.board, next_p)
    
    game.game_over, game.winner, game.current_player, game.valid_moves, game.score = over, winner, current, valid, count_score(game.board)

    # 3. Si es el turno de la IA, mover automáticamente
    if not game.game_over and game.current_player == 'white':
        ai_move = get_best_ai_move(game.board, 'white')
        if ai_move:
            game.board = apply_move(game.board, 'white', ai_move.row, ai_move.col)
            game.last_move = ai_move
            # Re-evaluar tras el turno de la IA
            over, winner, current, valid = resolve_game_state(game.board, 'black')
            game.game_over, game.winner, game.current_player, game.valid_moves, game.score = over, winner, current, valid, count_score(game.board)

    games_db[move_req.game_id] = game
    return game