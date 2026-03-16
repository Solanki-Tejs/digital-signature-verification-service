from fastapi import Depends, HTTPException, Request
from utils.jwt_token import decode_access_token


def get_current_user(request: Request):

    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
        return payload
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def role_required(allowed_roles: list):

    def checker(user=Depends(get_current_user)):

        if user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Not authorized")

        return user

    return checker