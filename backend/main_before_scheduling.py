import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from database import get_db
from models import User


# Load environment variables from backend/.env
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing. Check your backend/.env file."
    )

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# Initialize FastAPI
app = FastAPI(
    title="Smart Examination Management System",
    description="An Agentic AI-based examination management platform",
    version="1.0.0",
)


# Initialize password hashing
password_hash = PasswordHash.recommended()


# Read JWT bearer tokens from the Authorization header
bearer_scheme = HTTPBearer()


# Registration request model
class UserRegistration(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["student", "faculty", "admin", "invigilator"]


# Login request model
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# Create a JWT access token
def create_access_token(user_email: str) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_email,
        "exp": expiration,
    }

    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

    return token


# Home endpoint
@app.get("/")
def home():
    return {
        "message": "Smart Examination Management System API is running!",
        "status": "success",
    }


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}


# User registration endpoint
@app.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(
    user: UserRegistration,
    db: Session = Depends(get_db),
):
    # Check whether the email is already registered
    existing_user = (
        db.query(User)
        .filter(User.email == str(user.email))
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Hash the password
    hashed_password = password_hash.hash(user.password)

    # Create the user
    new_user = User(
        name=user.name,
        email=str(user.email),
        password_hash=hashed_password,
        role=user.role,
    )

    # Save the user to PostgreSQL
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
        "role": new_user.role,
    }


# User login endpoint
@app.post("/login")
def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    # Find the user by email
    user = (
        db.query(User)
        .filter(User.email == str(credentials.email))
        .first()
    )

    # Reject unknown users or incorrect passwords
    if user is None or not password_hash.verify(
        credentials.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate an access token
    access_token = create_access_token(str(user.email))

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
    }


# Get the currently authenticated user
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract the token from the Authorization header
    token = credentials.credentials

    try:
        # Decode and verify the JWT
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        user_email = payload.get("sub")

        if not user_email:
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    # Find the user associated with the token
    user = (
        db.query(User)
        .filter(User.email == user_email)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user


# Protected endpoint
@app.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
    }