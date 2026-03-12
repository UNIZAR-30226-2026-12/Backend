# from fastapi import APIRouter, HTTPException
# from game.schemas import GameStateResponse
# from game.manager import game_manager

# router = APIRouter()

# @router.post("/partida", response_model=GameStateResponse)
# async def create_game():
#     game_id = game_manager.create_game()
#     state = game_manager.get_game_state(game_id)
#     return state