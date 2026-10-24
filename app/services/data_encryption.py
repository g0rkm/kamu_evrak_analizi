import base64
import hashlib
import os
import threading
from datetime import datetime


class DataEncryption:
    def __init__(self, secret_key: str = None):
        self._lock = threading.Lock()
        self._stats = {"encrypted": 0, "decrypted": 0, "hash_computed": 0}
        if secret_key:
            self._key = self._derive_key(secret_key)
        else:
            self._key = self._derive_key("default-kamu-evrak-key-2024")
    
    @staticmethod
    def _derive_key(secret: str) -> bytes:
        return hashlib.sha256(secret.encode()).digest()
    
    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        iv = os.urandom(16)
        key_hash = hashlib.sha256(self._key).digest()[:16]
        encrypted = bytearray()
        plaintext_bytes = plaintext.encode("utf-8")
        for i, byte in enumerate(plaintext_bytes):
            encrypted.append(byte ^ key_hash[i % len(key_hash)] ^ iv[i % len(iv)])
        result = base64.b64encode(iv + bytes(encrypted)).decode("ascii")
        with self._lock:
            self._stats["encrypted"] += 1
        return result
    
    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        try:
            raw = base64.b64decode(ciphertext)
            iv = raw[:16]
            encrypted = raw[16:]
            key_hash = hashlib.sha256(self._key).digest()[:16]
            decrypted = bytearray()
            for i, byte in enumerate(encrypted):
                decrypted.append(byte ^ key_hash[i % len(key_hash)] ^ iv[i % len(iv)])
            with self._lock:
                self._stats["decrypted"] += 1
            return decrypted.decode("utf-8")
        except Exception:
            return ""
    
    def compute_hash(self, data: str, algorithm: str = "sha256") -> str:
        if algorithm == "sha256":
            h = hashlib.sha256(data.encode()).hexdigest()
        elif algorithm == "sha512":
            h = hashlib.sha512(data.encode()).hexdigest()
        elif algorithm == "md5":
            h = hashlib.md5(data.encode()).hexdigest()
        else:
            h = hashlib.sha256(data.encode()).hexdigest()
        with self._lock:
            self._stats["hash_computed"] += 1
        return h
    
    def verify_hash(self, data: str, expected_hash: str, algorithm: str = "sha256") -> bool:
        return self.compute_hash(data, algorithm) == expected_hash
    
    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._stats)
