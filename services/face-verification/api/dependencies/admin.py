from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from adapters.core_api_student_profile_client import (
    CoreApiAdministratorRequiredError,
    CoreApiStudentProfileClient,
    CoreApiUnauthorizedError,
    CoreApiUnavailableError,
)
from api.dependencies.auth import BEARER_CHALLENGE, bearer_scheme


async def get_current_administrator_id(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
) -> UUID:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A bearer access token is required.",
            headers=BEARER_CHALLENGE,
        )

    client = getattr(request.app.state, "core_api_student_profile_client", None)
    if not isinstance(client, CoreApiStudentProfileClient):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is unavailable",
        )

    try:
        user = await client.require_current_administrator(credentials.credentials)
    except CoreApiUnauthorizedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is not valid.",
            headers=BEARER_CHALLENGE,
        ) from error
    except CoreApiAdministratorRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The 'administrator' role is required.",
        ) from error
    except CoreApiUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify the administrator through the Core Backend.",
        ) from error

    return user.id


__all__ = ["get_current_administrator_id"]
