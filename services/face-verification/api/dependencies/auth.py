from uuid import UUID

from fastapi import HTTPException, status


async def get_current_student_id() -> UUID:

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Authentication is required",)


__all__ = ["get_current_student_id"]
