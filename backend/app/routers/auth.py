from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import uuid
from app.database import get_db
from app.models.user import User
from app.config import settings
from pydantic import BaseModel, EmailStr

print(">>> V4_FIX_ACTIVE: Loading auth.py from", __file__)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    grade_level: Optional[int] = 10

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # ✅ FIXED: Use string comparison instead of uuid.UUID object
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # ✅ FIXED: Check both email and username
    email_check = await db.execute(select(User).where(User.email == user_data.email))
    if email_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    username_check = await db.execute(select(User).where(User.username == user_data.username))
    if username_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    # ✅ FIXED: Password complexity validation
    password = user_data.password
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    
    # Check for at least one number or special character
    import re
    if not re.search(r"[0-9!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number or special character")

    # Argon2 handles any length automatically (no pre-hashing needed)
    try:
        user = User(
            email=user_data.email, username=user_data.username,
            hashed_password=pwd_context.hash(password),
            full_name=user_data.full_name, grade_level=user_data.grade_level,
            mastery_scores={}, embedding=[],
        )
        db.add(user)
        await db.flush()
        return Token(access_token=create_token(str(user.id)), token_type="bearer", user_id=str(user.id))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"[V4_ERROR] Database error: {str(e)}")

@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    try:
        # Passlib 1.7.4 has issues identifying $2b$ hashes automatically.
        # Fallback to native bcrypt for $2b$ hashes.
        if user.hashed_password.startswith("$2b$"):
            is_valid = bcrypt.checkpw(form.password.encode('utf-8'), user.hashed_password.encode('utf-8'))
        else:
            is_valid = pwd_context.verify(form.password, user.hashed_password)
    except Exception as e:
        is_valid = False
        
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    return Token(access_token=create_token(str(user.id)), token_type="bearer", user_id=str(user.id))
