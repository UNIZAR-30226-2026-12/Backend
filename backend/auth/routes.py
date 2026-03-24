from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from persistence.database import database
from auth.schemas import UserCreate, UserResponse, Token
from auth.security import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    try:
        username = user.username.strip()
        email = user.email.strip()
        if not username:
            raise HTTPException(status_code=400, detail="El nombre de usuario no puede estar vacío")

        query = "SELECT * FROM users WHERE username = :un OR email = :em"
        existing_user = await database.fetch_one(query=query, values={"un": username, "em": email})
        if existing_user:
            if existing_user["username"] == username:
                raise HTTPException(status_code=400, detail="Este nombre de usuario ya está registrado")
            if existing_user["email"] == email:
                raise HTTPException(status_code=400, detail="Este correo electrónico ya está registrado")
        
        hashed_password = get_password_hash(user.password)
        query = "INSERT INTO users (username, email, password_hash, elo) VALUES (:un, :em, :pw, :elo)"
        await database.execute(query=query, values={"un": username, "em": email, "pw": hashed_password, "elo": 1000})
        
        query = "SELECT id, username, email, elo, avatar_url, preferred_piece_color, preferred_board_color FROM users WHERE username = :un"
        return await database.fetch_one(query=query, values={"un": username})
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error al registrar: {str(e)}")

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    login_id = form_data.username.strip()
    if not login_id:
        raise HTTPException(status_code=400, detail="Usuario/Correo o contraseña incorrectos")

    query = "SELECT * FROM users WHERE email = :login_id OR username = :login_id"
    user = await database.fetch_one(query=query, values={"login_id": login_id})

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Usuario/Correo o contraseña incorrectos")
    access_token = create_access_token(
        data={"sub": str(user["id"])}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}
