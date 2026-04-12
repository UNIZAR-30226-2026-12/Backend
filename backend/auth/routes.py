from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta
import random
import string
from persistence.database import database
from auth.schemas import UserCreate, UserResponse, Token, ForgotPasswordRequest, ResetPasswordRequest
from auth.security import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from auth.email_service import send_reset_email

router = APIRouter()

# Almacén temporal de códigos de reset: {email: {"code": str, "expires": datetime}}
reset_codes: dict = {}

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


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    email = request.email.strip().lower()

    query = "SELECT id FROM users WHERE LOWER(email) = :email"
    user = await database.fetch_one(query=query, values={"email": email})

    if not user:
        raise HTTPException(status_code=404, detail="No hay ninguna cuenta asociada a este correo electrónico")

    code = ''.join(random.choices(string.digits, k=6))
    reset_codes[email] = {
        "code": code,
        "expires": datetime.utcnow() + timedelta(minutes=15)
    }

    try:
        await send_reset_email(email, code)
    except Exception as e:
        del reset_codes[email]
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo: {str(e)}")

    return {"message": "Correo de recuperación enviado"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    email = request.email.strip().lower()

    stored = reset_codes.get(email)
    if not stored:
        raise HTTPException(status_code=400, detail="No se ha solicitado un restablecimiento para este correo")

    if datetime.utcnow() > stored["expires"]:
        del reset_codes[email]
        raise HTTPException(status_code=400, detail="El código ha expirado. Solicita uno nuevo")

    if stored["code"] != request.code.strip():
        raise HTTPException(status_code=400, detail="Código incorrecto")

    hashed_password = get_password_hash(request.new_password)
    query = "UPDATE users SET password_hash = :pw WHERE email = :email"
    await database.execute(query=query, values={"pw": hashed_password, "email": email})

    del reset_codes[email]

    return {"message": "Contraseña restablecida correctamente"}
