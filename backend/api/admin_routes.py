from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.api.limiter import limiter
from backend.auth.dependencies import require_admin
from backend.auth.service import generate_temp_password
from backend.pocketbase.client import PocketBaseClient, get_pb_client
from backend.users.models import User
from backend.users.repository import UserRepository
from backend.users.schemas import UserCreate, UserResponse, UserWithTempPassword

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
@limiter.limit("30/minute")
async def list_users(
    request: Request,
    pb: PocketBaseClient = Depends(get_pb_client),
    _: User = Depends(require_admin),
) -> list[User]:
    return UserRepository(pb).list_all()


@router.post(
    "/users", response_model=UserWithTempPassword, status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/minute")
async def create_user(
    request: Request,
    body: UserCreate,
    pb: PocketBaseClient = Depends(get_pb_client),
    _: User = Depends(require_admin),
) -> UserWithTempPassword:
    repo = UserRepository(pb)
    if repo.get_by_username(body.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce nom d'utilisateur est déjà pris",
        )
    temp_password = generate_temp_password()
    user = repo.create(body.username, temp_password)
    return UserWithTempPassword(
        user=UserResponse.model_validate(user), temp_password=temp_password
    )


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_user(
    request: Request,
    username: str,
    pb: PocketBaseClient = Depends(get_pb_client),
    admin: User = Depends(require_admin),
) -> None:
    if username == admin.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer son propre compte",
        )
    repo = UserRepository(pb)
    user = repo.get_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable"
        )
    repo.delete(user)
