import json
from cryptography.fernet import Fernet

class EmbeddingCrypto:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("utf-8"))

    def encrypt(self, embedding: list[float]) -> bytes:
        payload = json.dumps(embedding, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(payload)

    def decrypt(self, token: bytes) -> tuple[float, ...]:
        payload = self._fernet.decrypt(token)
        values = json.loads(payload.decode("utf-8"))
        return tuple(float(v) for v in values)