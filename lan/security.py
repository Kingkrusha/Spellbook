"""TLS plumbing: a throwaway certificate per session, and the SSL contexts.

Python's ``ssl`` module can use certificates but not create them, so the host makes a
self-signed one with the ``cryptography`` package each time a session starts. Nobody
trusts it through a certificate authority; clients *pin* it instead - the invite code
contains its fingerprint (see :mod:`lan.protocol`) and a client that sees any other
certificate disconnects before sending a byte.
"""

from __future__ import annotations

import datetime
import os
import ssl
import tempfile
from typing import Tuple

from lan.protocol import fingerprint_of


def generate_session_cert() -> Tuple[bytes, bytes, str]:
    """Return ``(cert_pem, key_pem, fingerprint)`` for a fresh self-signed certificate."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Spellbook LAN session")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(hours=1))
        .not_valid_after(now + datetime.timedelta(days=2))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem, fingerprint_of(cert.public_bytes(serialization.Encoding.DER))


def server_context(cert_pem: bytes, key_pem: bytes) -> ssl.SSLContext:
    """TLS 1.3 server context. ``load_cert_chain`` wants files, so the key touches disk
    only for the instant it takes to load it."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    fd_c, cert_path = tempfile.mkstemp(suffix=".pem")
    fd_k, key_path = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd_c, "wb") as f:
            f.write(cert_pem)
        with os.fdopen(fd_k, "wb") as f:
            f.write(key_pem)
        ctx.load_cert_chain(cert_path, key_path)
    finally:
        for path in (cert_path, key_path):
            try:
                os.remove(path)
            except OSError:
                pass
    return ctx


def client_context() -> ssl.SSLContext:
    """TLS 1.3 client context that accepts any certificate *at the TLS layer*.

    That is deliberate: the certificate is checked right after the handshake against
    the fingerprint from the invite (``protocol.pinned_fingerprint_ok``), and nothing
    is sent before that check passes.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
