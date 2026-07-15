from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from services import auth_service

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    username: str
    full_name: str
    phone_number: str
    password: str


class RegisterResponse(BaseModel):
    id: int
    email: str


@router.post("/auth/register", response_model=RegisterResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    user = await auth_service.register(
        session,
        email=payload.email,
        username=payload.username,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        password=payload.password,
    )
    return RegisterResponse(id=user.id, email=user.email)
