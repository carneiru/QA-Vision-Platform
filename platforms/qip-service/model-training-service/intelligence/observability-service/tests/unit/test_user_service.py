from src.observability-service.service.user_service import UserService
from auth.schemas.user import UserCreate

def test_create_user(db):
    user_in = UserCreate(
        email="test@example.com",
        password="securepassword123",
        full_name="Test User"
    )
    user = UserService.create_user(db, user_in)
    assert user.email == user_in.email
    assert user.full_name == user_in.full_name
    assert user.hashed_password is not None
    assert user.id is not None

def test_duplicate_email(db):
    user_in = UserCreate(
        email="test@example.com",
        password="securepassword123",
        full_name="Test User"
    )
    UserService.create_user(db, user_in)
    
    # Try to create another user with same email
    try:
        UserService.create_user(db, user_in)
        assert False, "Should have raised HTTPException"
    except Exception as e:
        assert "Email already registered" in str(e)

def test_authenticate_user(db):
    user_in = UserCreate(
        email="test@example.com",
        password="securepassword123",
        full_name="Test User"
    )
    user = UserService.create_user(db, user_in)
    
    authenticated = UserService.authenticate_user(db, user_in.email, user_in.password)
    assert authenticated is not None
    assert authenticated.email == user_in.email
    
    # Wrong password
    assert UserService.authenticate_user(db, user_in.email, "wrong") is None
    
    # Non-existent email
    assert UserService.authenticate_user(db, "nonexistent@example.com", "anything") is None
