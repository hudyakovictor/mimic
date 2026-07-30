"""Password hashing with Argon2id and legacy bcrypt verification.

New credentials use OWASP's memory-hard Argon2id profile. ``BcryptHasher`` is
kept second only so installations can verify hashes created by MimicGuard
0.1; successful login can later persist ``verify_and_update()``'s replacement.
"""

from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("Password must not be empty")
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hash.verify(plain, hashed)
    except (TypeError, ValueError):
        return False
