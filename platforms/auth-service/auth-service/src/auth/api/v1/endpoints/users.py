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
        # An account created through SSO has no password to confirm. Setting a first one is
        # allowed; replacing an existing one requires proving you know it.
        if current_user.hashed_password is not None:
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
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user doesn't have enough privileges"
        )
    return user
