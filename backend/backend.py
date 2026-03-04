import uuid
from typing import List, Optional, Literal, Dict, Tuple
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import copy
from db import database
from passlib.context import CryptContext
import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta

app = FastAPI(title="Reversi AI Backend")

# Habilitar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# --- Configuración Auth ---
SECRET_KEY = "supersecretkey_reversi" # En prod usar variable de entorno
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 semana

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    
    query = "SELECT * FROM users WHERE username = :username"
    user = await database.fetch_one(query=query, values={"username": username})
    if user is None:
        raise credentials_exception
    return dict(user)

# --- Tipos y Constantes ---
Player = Literal['black', 'white']
Cell = Optional[Player]
Board = List[List[Cell]]
BOARD_SIZE = 8

POSITION_WEIGHTS = [
    [100, -20, 10, 5, 5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [10, -2, -1, -1, -1, -1, -2, 10],
    [5, -2, -1, -1, -1, -1, -2, 5],
    [5, -2, -1, -1, -1, -1, -2, 5],
    [10, -2, -1, -1, -1, -1, -2, 10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10, 5, 5, 10, -20, 100]
]

DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1)
]

# --- Modelos de Datos ---

class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    elo: int
    avatar_url: Optional[str] = None
    preferred_piece_color: str
    preferred_board_color: str

class Token(BaseModel):
    access_token: str
    token_type: str

class Coordinate(BaseModel):
    row: int
    col: int

class GameStateResponse(BaseModel):
    game_id: str
    board: Board
    current_player: Optional[Player]
    winner: Optional[str]
    game_over: bool
    score: Dict[str, int]
    valid_moves: List[Coordinate]
    last_move: Optional[Coordinate] = None

class MoveRequest(BaseModel):
    game_id: str
    row: int
    col: int
    player: Player

# --- DB en memoria ---
games_db: Dict[str, GameStateResponse] = {}

# --- Lógica de Juego ---

def create_initial_board() -> Board:
    board = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    mid = BOARD_SIZE // 2
    board[mid - 1][mid - 1] = 'white'
    board[mid][mid] = 'white'
    board[mid - 1][mid] = 'black'
    board[mid][mid - 1] = 'black'
    return board

def is_on_board(r: int, c: int) -> bool:
    return 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE

def get_valid_moves(board: Board, player: Player) -> List[Coordinate]:
    moves = []
    if not player: return moves
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if is_valid_move(board, player, r, c):
                moves.append(Coordinate(row=r, col=c))
    return moves

def is_valid_move(board: Board, player: Player, row: int, col: int) -> bool:
    if board[row][col] is not None: return False
    opponent = 'white' if player == 'black' else 'black'
    for dr, dc in DIRECTIONS:
        r, c = row + dr, col + dc
        found_opponent = False
        while is_on_board(r, c):
            cell = board[r][c]
            if cell == opponent: found_opponent = True
            elif cell == player:
                if found_opponent: return True
                break
            else: break
            r += dr
            c += dc
    return False

def apply_move(board: Board, player: Player, row: int, col: int) -> Board:
    new_board = copy.deepcopy(board)
    new_board[row][col] = player
    opponent = 'white' if player == 'black' else 'black'
    for dr, dc in DIRECTIONS:
        r, c = row + dr, col + dc
        to_flip = []
        while is_on_board(r, c):
            cell = new_board[r][c]
            if cell == opponent: to_flip.append((r, c))
            elif cell == player:
                for fr, fc in to_flip: new_board[fr][fc] = player
                break
            else: break
            r += dr
            c += dc
    return new_board

def count_score(board: Board) -> Dict[str, int]:
    return {
        "black": sum(row.count('black') for row in board),
        "white": sum(row.count('white') for row in board)
    }

# --- Motor IA ---

def evaluate_board(board: Board, player: Player) -> int:
    opponent = 'white' if player == 'black' else 'black'
    score = 0
    counts = count_score(board)
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] == player: score += POSITION_WEIGHTS[r][c]
            elif board[r][c] == opponent: score -= POSITION_WEIGHTS[r][c]
    
    my_moves = len(get_valid_moves(board, player))
    op_moves = len(get_valid_moves(board, opponent))
    score += (my_moves - op_moves) * 15 # Priorizar movilidad
    return score

def minimax(board: Board, depth: int, alpha: float, beta: float, maximizing: bool, ai_player: Player) -> float:
    human_player = 'black' if ai_player == 'white' else 'white'
    current_p = ai_player if maximizing else human_player
    
    moves = get_valid_moves(board, current_p)
    
    if depth == 0 or not moves:
        return evaluate_board(board, ai_player)
    
    if maximizing:
        max_eval = float('-inf')
        for m in moves:
            new_board = apply_move(board, ai_player, m.row, m.col)
            eval_val = minimax(new_board, depth - 1, alpha, beta, False, ai_player)
            max_eval = max(max_eval, eval_val)
            alpha = max(alpha, eval_val)
            if beta <= alpha: break
        return max_eval
    else:
        min_eval = float('inf')
        for m in moves:
            new_board = apply_move(board, human_player, m.row, m.col)
            eval_val = minimax(new_board, depth - 1, alpha, beta, True, ai_player)
            min_eval = min(min_eval, eval_val)
            beta = min(beta, eval_val)
            if beta <= alpha: break
        return min_eval

def get_best_ai_move(board: Board, player: Player) -> Optional[Coordinate]:
    valid = get_valid_moves(board, player)
    if not valid: return None
    best_val, best_move = float('-inf'), valid[0]
    for m in valid:
        new_board = apply_move(board, player, m.row, m.col)
        val = minimax(new_board, 3, float('-inf'), float('inf'), False, player)
        if val > best_val:
            best_val, best_move = val, m
    return best_move

def resolve_game_state(board: Board, next_player: Player) -> Tuple[bool, Optional[str], Optional[Player], List[Coordinate]]:
    moves = get_valid_moves(board, next_player)
    if moves:
        return False, None, next_player, moves
    
    other_player = 'white' if next_player == 'black' else 'black'
    other_moves = get_valid_moves(board, other_player)
    if other_moves:
        return False, None, other_player, other_moves
    
    # Si nadie puede mover, fin del juego
    counts = count_score(board)
    winner = 'draw'
    if counts['black'] > counts['white']: winner = 'black'
    elif counts['white'] > counts['black']: winner = 'white'
    return True, winner, None, []

# --- Endpoints API ---

# --- Auth y Usuarios ---

@app.post("/api/auth/register", response_model=UserResponse)
async def register(user: UserCreate):
    query = "SELECT * FROM users WHERE username = :username"
    existing_user = await database.fetch_one(query=query, values={"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    query = """
        INSERT INTO users (username, password_hash)
        VALUES (:username, :password)
        RETURNING id, username, elo, avatar_url, preferred_piece_color, preferred_board_color
    """
    values = {"username": user.username, "password": hashed_password}
    return await database.fetch_one(query=query, values=values)

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    query = "SELECT * FROM users WHERE username = :username"
    user = await database.fetch_one(query=query, values={"username": form_data.username})
    
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(
        data={"sub": user["username"]}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/users/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

@app.get("/api/users/{user_id}/stats")
async def read_user_stats(user_id: int):
    query = "SELECT elo, username FROM users WHERE id = :user_id"
    user = await database.fetch_one(query=query, values={"user_id": user_id})
    if not user:
         raise HTTPException(status_code=404, detail="User not found")
    
    query_games = "SELECT COUNT(*) as total, SUM(CASE WHEN winner_id = :user_id THEN 1 ELSE 0 END) as wins FROM games WHERE player1_id = :user_id OR player2_id = :user_id"
    stats = await database.fetch_one(query=query_games, values={"user_id": user_id})
    
    return {
        "username": user["username"],
        "elo": user["elo"],
        "total_games": stats["total"] if stats else 0,
        "wins": stats["wins"] if stats and stats["wins"] else 0
    }

# --- Partidas (Mock Anterior) ---

@app.post("/partida", response_model=GameStateResponse)
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

@app.post("/movimiento", response_model=GameStateResponse)
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
