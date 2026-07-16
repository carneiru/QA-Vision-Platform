from src.automation-service.utils.password import get_password_hash, verify_password
from src.automation-service.utils.tokens import create_access_token, decode_token

def test_password_hashing():
    password = "securepassword123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrongpassword", hashed)

def test_token_creation_and_decoding():
    data = {"sub": "123"}
    token = create_access_token(data)
    decoded = decode_token(token)
    assert decoded["sub"] == "123"
