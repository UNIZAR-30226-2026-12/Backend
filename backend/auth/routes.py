import secrets
import string
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from persistence.database import database
from auth.schemas import UserCreate, UserResponse, Token, ForgotPasswordRequest
from auth.security import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from auth.email_service import send_new_password_email

router = APIRouter()


def _generate_password(length: int = 8) -> str:
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%&*-_+=?"

    password_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
    ]
    full_charset = lowercase + uppercase + digits + symbols
    password_chars += [secrets.choice(full_charset) for _ in range(length - 3)]

    rng = secrets.SystemRandom()
    rng.shuffle(password_chars)
    return "".join(password_chars)


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
    generic_response = {"message": "Si el correo existe, recibirás una nueva contraseña"}
    email = request.email.strip().lower()

    query = "SELECT id, email FROM users WHERE LOWER(email) = :email"
    user = await database.fetch_one(query=query, values={"email": email})

    if not user:
        return generic_response

    new_password = _generate_password()
    hashed_password = get_password_hash(new_password)

    update_query = "UPDATE users SET password_hash = :pw WHERE id = :id"
    await database.execute(query=update_query, values={"pw": hashed_password, "id": user["id"]})

    try:
        await send_new_password_email(user["email"], new_password)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar el correo: {str(e)}")

    return generic_response
