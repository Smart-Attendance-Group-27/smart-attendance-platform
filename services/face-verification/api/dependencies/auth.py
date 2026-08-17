from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from adapters.core_api_student_profile_client import (
    CoreApiForbiddenError,
    CoreApiStudentProfileClient,
    CoreApiStudentProfileNotFoundError,
    CoreApiUnauthorizedError,
    CoreApiUnavailableError,
)


bearer_scheme = HTTPBearer(auto_error=False)
BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


async def get_current_student_id(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
) -> UUID:
    """Ask the Core Backend to authenticate and resolve the student profile."""

    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="A bearer access token is required.",headers=BEARER_CHALLENGE,)

    client = getattr(request.app.state,"core_api_student_profile_client",None,)

    if not isinstance(client, CoreApiStudentProfileClient):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail="Authentication is unavailable",)

    try:
        profile = await client.get_current_student_profile(credentials.credentials,)

    except CoreApiUnauthorizedError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Access token is not valid.",headers=BEARER_CHALLENGE,) from error

    except CoreApiForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="The 'student' role is required.",) from error

    except CoreApiStudentProfileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="No active student profile exists for this account.",) from error

    except CoreApiUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,detail="Could not resolve the student through the Core Backend.",) from error

    return profile.id


__all__ = ["get_current_student_id"]
