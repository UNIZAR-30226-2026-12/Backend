import os
import uuid
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException

# Subimos un nivel en los directorios para apuntar a backend/uploads/avatars
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVATARS_UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
os.makedirs(AVATARS_UPLOADS_DIR, exist_ok=True)

def save_user_avatar_file(user_id: int, file: UploadFile) -> Tuple[str, str]:
    allowed_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    _, extension = os.path.splitext(file.filename or "")
    extension = extension.lower()
    if extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Formato de archivo no permitido")

    file_name = f"{user_id}_{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(AVATARS_UPLOADS_DIR, file_name)
    public_path = f"/uploads/avatars/{file_name}"
    return file_path, public_path


def delete_avatar_file(avatar_url: Optional[str]) -> None:
    """Borra el fichero de avatar del disco si es un upload local."""
    if not avatar_url or "/uploads/avatars/" not in avatar_url:
        return
    file_name = avatar_url.split("/uploads/avatars/")[-1]
    if not file_name:
        return
    file_path = os.path.join(AVATARS_UPLOADS_DIR, file_name)
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass  # Ya no existía, no es un error
