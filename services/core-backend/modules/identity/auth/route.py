from fastapi import APIRouter, status

from modules.identity.auth.dependencies import CurrentUser
from modules.identity.auth.schemas import CurrentUserResponse

router = APIRouter(tags=["identity"])


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
)
async def read_current_user(current_user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.user_id,
        email=current_user.email,
        roles=list(current_user.roles),
    )
