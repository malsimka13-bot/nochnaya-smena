import os
import hmac
import hashlib
import secrets
import datetime as dt
import jwt
import dotenv

load_dotenv()

SECRET = os.getenv("SECRET_KEY")
if SECRET is None:
    raise ValueError("Ошибка: Переменная SECRET_KEY не задана в окружении!")
DEFAULT_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 из стандартной библиотеки. Формат: алгоритм$итерации$соль$хеш."""
    iterations = int(os.getenv("PBKDF2_ITERATIONS", DEFAULT_ITERATIONS))
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return algo == "pbkdf2_sha256" and hmac.compare_digest(calc.hex(), digest)
    except (ValueError, TypeError):
        return False


def make_token(user_id: int, hours: int = 12) -> str:
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET, algorithm="HS256")


def user_id_from_token(token: str):
    """Возвращает id пользователя или None, если токен неверный или просрочен."""
    try:
        return int(jwt.decode(token, SECRET, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
