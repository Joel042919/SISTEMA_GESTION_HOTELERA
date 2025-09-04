import bcrypt


def hash_password(plainPassword: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plainPassword.encode('utf-8'), salt).decode('utf-8')


def verify_password(plainPassword: str, hashed_password: str) -> bool:
    """Verify a password against its hash using bcrypt"""
    return bcrypt.checkpw(plainPassword.encode('utf-8'), hashed_password.encode('utf-8'))