import base64
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from persistence.database import database
from auth.dependencies import get_current_user

router = APIRouter()

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Formato de archivo no permitido")

    content = await file.read()

    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="El archivo no puede superar los 2 MB")

    # Guardamos como data URL base64 directamente en la BD
    encoded = base64.b64encode(content).decode("utf-8")
    avatar_url = f"data:{file.content_type};base64,{encoded}"

    await database.execute(
        "UPDATE users SET avatar_url = :avatar WHERE id = :uid",
        values={"avatar": avatar_url, "uid": current_user["id"]},
    )
    return {"avatar_url": avatar_url}