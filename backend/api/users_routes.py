from fastapi import APIRouter, Depends, Request

from backend.api.limiter import limiter
from backend.auth.dependencies import get_current_user
from backend.users.models import User
from backend.users.schemas import UserStatsResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/stats", response_model=UserStatsResponse)
@limiter.limit("60/minute")
async def my_stats(
    request: Request, current_user: User = Depends(get_current_user)
) -> UserStatsResponse:
    return UserStatsResponse.model_validate(current_user)
