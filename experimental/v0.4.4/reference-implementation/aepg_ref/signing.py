"""Ed25519 signing for receipts and revocation heartbeats.

Signers hold private keys. Verifiers hold only public keys, so a component
that can check a signature cannot produce one. Keys are derived
deterministically from a seed for reproducible experiments; production keys
come from an HSM or key service.
"""
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .canonical import canonical_json


def private_key_from_seed(seed: bytes) -> Ed25519PrivateKey:
    if not isinstance(seed, (bytes, bytearray)) or len(seed) < 16:
        raise ValueError("seed must be at least 16 bytes")
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed).digest())


class Verifier:
    def __init__(self, public_key: Ed25519PublicKey, key_id: str):
        self._pub = public_key
        self.key_id = key_id

    def verify(self, signed) -> bool:
        if not isinstance(signed, dict) or signed.get("key_id") != self.key_id or "sig" not in signed:
            return False
        body = {k: v for k, v in signed.items() if k != "sig"}
        try:
            self._pub.verify(bytes.fromhex(signed["sig"]), canonical_json(body))
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False


class Signer:
    def __init__(self, seed: bytes, key_id: str):
        self._priv = private_key_from_seed(seed)
        self.key_id = key_id

    def sign(self, body: dict) -> dict:
        body = dict(body, key_id=self.key_id)
        return dict(body, sig=self._priv.sign(canonical_json(body)).hex())

    def verifier(self) -> Verifier:
        return Verifier(self._priv.public_key(), self.key_id)

    def verify(self, signed) -> bool:
        return self.verifier().verify(signed)
