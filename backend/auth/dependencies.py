import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException
from auth.security import oauth2_scheme, SECRET_KEY, ALGORITHM
from persistence.database import database

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Validación para rutas REST """
    credentials_exception = HTTPException(
        status_code=401,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    
    query = "SELECT * FROM users WHERE id = :uid"
    user = await database.fetch_one(query=query, values={"uid": int(user_id)})
    if user is None:
        raise credentials_exception
    return dict(user)


async def verify_token_ws(token: str):
    """Validación para WebSockets"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            return None
            
    except InvalidTokenError:
        #Si el token es falso o ha caducado, devolvemos None
        return None
    
    #Buscamos al usuario en la base de datos
    query = "SELECT * FROM users WHERE id = :uid"
    user = await database.fetch_one(query=query, values={"uid": int(user_id)})
    
    if user is None:
        return None
        
    return dict(user)