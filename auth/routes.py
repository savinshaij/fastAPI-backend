from typing import Optional
from fastapi import APIRouter, Query, status, HTTPException, Body
from fastapi.responses import RedirectResponse
import httpx, secrets
from config import *
from auth.utils import create_jwt
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from models.user import UserCreate, UserLogin, UserOut

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
client = AsyncIOMotorClient(MONGO_URI)
db = client.myapp

@router.post("/register", response_model=UserOut)
async def register(user: UserCreate):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=409, detail="User already exists.")

    hashed_pw = pwd_context.hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_pw
    user_dict["picture"] = "null"
    await db.users.insert_one(user_dict)
    return UserOut(name=user.name, email=user.email, picture="null")

@router.post("/login")
async def login(user: UserLogin):
    db_user = await db.users.find_one({"email": user.email})
    if not db_user or "password" not in db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    if not pwd_context.verify(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    jwt_token = create_jwt({
        "email": db_user["email"],
        "name": db_user.get("name", ""),
        "picture": db_user.get("picture", ""),
    })

    return {"token": jwt_token}

@router.get("/login")
async def login_google():
    state = secrets.token_urlsafe(16)
    return RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"state={state}"
    )

@router.get("/callback")
async def callback(
    code: Optional[str] = Query(None),
    state: str = "",
    error: Optional[str] = Query(None),
):
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login")

    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_res.raise_for_status()
            tokens = token_res.json()
            id_token = tokens.get("id_token")
            if not id_token:
                return RedirectResponse(f"{FRONTEND_URL}/login")

            userinfo_res = await client.get(
                f"https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={id_token}"
            )
            userinfo_res.raise_for_status()
            user = userinfo_res.json()

    except httpx.HTTPError:
        return RedirectResponse(f"{FRONTEND_URL}/login")

    if not user.get("email"):
        return RedirectResponse(f"{FRONTEND_URL}/login")

    existing = await db.users.find_one({"email": user["email"]})
    if not existing:
        await db.users.insert_one({
            "name": user.get("name", ""),
            "email": user.get("email"),
            "picture": user.get("picture", ""),
        })

    jwt_token = create_jwt({
        "email": user["email"],
        "name": user.get("name", ""),
        "picture": user.get("picture", ""),
    })

    return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={jwt_token}")
