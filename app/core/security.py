from passlib.hash import pbkdf2_sha256


def hash_password(plainPassword: str) -> str:
    return pbkdf2_sha256.hash(plainPassword)


def verify_password(plainPassword: str, hashed_password: str) -> bool:
    return pbkdf2_sha256.verify(plainPassword,hashed_password)