import bcrypt


def create_password_hash(password: str) -> str:
    """
    Hash a plain password and return string version
    Safe to store in VARCHAR(255)
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)  # 12 is secure default
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare user input password with stored hash
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )
