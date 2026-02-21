import logging
from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.models import User

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Зависимость для получения текущего пользователя через Cookie
def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == int(user_id)).first()
    return user

# Зависимость: Требуется авторизация (любая)
def require_user(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user

# Зависимость: Требуется Админ
def require_admin(user = Depends(get_current_user)):
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    return user