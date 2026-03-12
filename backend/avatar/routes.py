from fastapi import APIRouter, UploadFile, File, Request, Depends
from persistence.database import database
from auth.dependencies import get_current_user
from avatar.utils import save_user_avatar_file

router = APIRouter()

@router.post("/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    file_path, public_path = save_user_avatar_file(current_user["id"], file)
    content = await file.read()

    with open(file_path, "wb") as avatar_file:
        avatar_file.write(content)

    avatar_url = f"{str(request.base_url).rstrip('/')}{public_path}"
    query_update = "UPDATE users SET avatar_url = :avatar WHERE id = :uid"
    await database.execute(query=query_update, values={"avatar": avatar_url, "uid": current_user["id"]})
    return {"avatar_url": avatar_url}