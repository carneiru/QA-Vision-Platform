from sqlalchemy.orm import Session
from src.auth.models.user import User
from src.auth.schemas.user import UserCreate, UserUpdate
from src.auth.utils.password import get_password_hash
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

class UserService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        # This read `filter(user_id == user_id)` -- a Python tautology evaluating to True,
        # so SQLAlchemy emitted `WHERE true` and returned the FIRST user row for every id.
        # /auth/refresh-token resolved identities through here, so any user could refresh
        # into an access token for users.id == 1, and PUT /users/me could overwrite that
        # account (password included).
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_users(db: Session, skip: int = 0, limit: int = 100) -> list:
        return db.query(User).offset(skip).limit(limit).all()

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_in.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create new user
        user = User(
            email=user_in.email,
            # SSO-created users have no password; the column is nullable for exactly that.
            # Hashing None raises, which made every first-time SSO login fail.
            hashed_password=get_password_hash(user_in.password) if user_in.password else None,
            full_name=user_in.full_name,
            is_active=True
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        user = UserService.get_user_by_email(db, email)
        if not user:
            return None
        if not user.hashed_password:
            return None  # SSO-only user
        from src.auth.utils.password import verify_password
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def update_user(db: Session, user_id: int, user_in: UserUpdate, allow_privileged: bool = False) -> User:
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found"
            )

        update_data = user_in.dict(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        # Defence in depth behind UserSelfUpdate: this loop setattr's whatever it is handed,
        # so a caller passing a schema that carries is_superuser would escalate silently.
        # Privileged fields must be opted into explicitly by an admin-only caller.
        if not allow_privileged:
            for privileged in ("is_superuser", "is_active"):
                update_data.pop(privileged, None)

        for field, value in update_data.items():
            setattr(user, field, value)

        db.add(user)
        db.commit()
        db.refresh(user)
        return user

# Import for use in other modules
from src.auth.utils.password import verify_password