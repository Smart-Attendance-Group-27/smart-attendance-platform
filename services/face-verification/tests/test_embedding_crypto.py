import pytest
from cryptography.fernet import Fernet, InvalidToken

from core.embedding_crypto import EmbeddingCrypto


def create_crypto() -> EmbeddingCrypto:
    key = Fernet.generate_key().decode("utf-8")
    return EmbeddingCrypto(key)


def test_encrypts_and_decrypts_embedding() -> None:
    crypto = create_crypto()
    original_embedding = [0.1, -0.2, 0.3]

    encrypted = crypto.encrypt(original_embedding)
    decrypted = crypto.decrypt(encrypted)

    assert isinstance(encrypted, bytes)
    assert decrypted == pytest.approx(original_embedding)


def test_encrypted_value_does_not_contain_plain_embedding() -> None:
    crypto = create_crypto()
    embedding = [0.123456, 0.654321]

    encrypted = crypto.encrypt(embedding)

    assert b"0.123456" not in encrypted
    assert b"0.654321" not in encrypted


def test_same_embedding_produces_different_ciphertext() -> None:
    crypto = create_crypto()
    embedding = [0.1, 0.2, 0.3]

    first = crypto.encrypt(embedding)
    second = crypto.encrypt(embedding)

    assert first != second
    assert crypto.decrypt(first) == pytest.approx(embedding)
    assert crypto.decrypt(second) == pytest.approx(embedding)


def test_rejects_modified_ciphertext() -> None:
    crypto = create_crypto()
    encrypted = bytearray(crypto.encrypt([0.1, 0.2, 0.3]))

    encrypted[-10] ^= 1

    with pytest.raises(InvalidToken):
        crypto.decrypt(bytes(encrypted))


def test_rejects_decryption_with_different_key() -> None:
    first_crypto = create_crypto()
    second_crypto = create_crypto()

    encrypted = first_crypto.encrypt([0.1, 0.2, 0.3])

    with pytest.raises(InvalidToken):
        second_crypto.decrypt(encrypted)