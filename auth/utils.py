import jwt
from datetime import datetime, timedelta
from config import JWT_SECRET

def create_jwt(data: dict):
    payload = {
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
        "sub": data
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_jwt(token: str):
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
