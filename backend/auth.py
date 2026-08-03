# backend/auth.py
from fastapi import Header, HTTPException
from config import API_KEY


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
