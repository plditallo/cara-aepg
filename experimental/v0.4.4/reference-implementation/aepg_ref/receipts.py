"""Signed pre-action receipts (AEPG-EVID-005, AEPG-DEC-005/006/007/008).

v0.4.3: Ed25519. The PEP holds the private key; the actuator is given only a
Verifier (ReceiptSigner.verifier()) and cannot mint receipts.
"""
from .signing import Signer, Verifier


class ReceiptSigner(Signer):
    pass


ReceiptVerifier = Verifier
