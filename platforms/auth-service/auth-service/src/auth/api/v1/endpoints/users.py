from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from src.auth.api import deps
from src.auth.service.user_service import UserService
# UserInDB carries hashed_password; aliasing it as the response model leaked every user's
# bcrypt hash through /users/me, /users/ and /users/{id}. User is the public shape.
from src.auth.schemas.user import UserSelfUpdate, UserUpdate, User
from src.auth.models.user import User as UserModel
from src.auth.service.auth_service import AuthService
from src.auth.utils.password import verify_password

router = APIRouter()


@router.get("/", response_model=List[User])
def read_users(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_active_superuser),
):
    """
    Retrieve users. Only superusers can access this endpoint.
    """
    users = UserService.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/me", response_model=User)
def read_user_me(
    current_user: UserModel = Depends(deps.get_current_active_user),
):
    """
    Get current user.
    """
    return current_user


@router.put("/me", response_model=User)
def update_user_me(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserSelfUpdate,
    current_user: UserModel = Depends(deps.get_current_active_user),
):
    """
    Update own user.
    """
    changing_password = user_in.password is not None
    if changing_password:
        if current_user.hashed_password is None:
            # An SSO account has no password to confirm, so setting a first one used to be
            # allowed unconditionally -- which converted a stolen access token, valid for
            # days and revocable by nothing, into a permanent credential on the account.
            # Adding a password to an SSO account needs its own verified flow.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Setting a password on an SSO account is not supported yet",
            )
        if not user_in.current_password or not verify_password(
            user_in.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current_password is incorrect",
            )

    # current_password is a credential check, not a column. Rebuilding as UserUpdate from
    # only the fields the caller actually set keeps update_user's exclude_unset semantics --
    # an omitted field stays omitted rather than being written as None.
    user = UserService.update_user(
        db,
        current_user.id,
        UserUpdate(**user_in.model_dump(exclude_unset=True, exclude={"current_password"})),
    )

    if changing_password:
        # Changing a password is how someone reacts to a suspected compromise. Leaving the
        # attacker's refresh tokens live would make it ceremonial: they would keep minting
        # access tokens for up to 30 days.
        AuthService.revoke_all_user_sessions(db, current_user.id)

    return user


@router.get("/{user_id}", response_model=User)
def read_user_by_id(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: UserModel = Depends(deps.get_current_active_user),
):
    """
    Get a specific user by id.
    """
    user = UserService.get_user_by_id(db, user_id)
    if user is not None and user.id == current_user.id:
        return user
    if not current_user.is_superuser:
        # 403, not 400: the request is well-formed and the caller is authenticated, they are
        # just not allowed. get_current_active_superuser already answers 403 elsewhere.
        # Answered before the existence check so a non-superuser cannot probe which ids exist.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    if user is None:
        # Returning None into response_model=User raised ResponseValidationError -- a 500 for
        # an ordinary "no such id".
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
