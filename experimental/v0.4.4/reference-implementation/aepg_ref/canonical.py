import hashlib, json

def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha256_uri(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()

def verify_hash(value, expected: str) -> bool:
    return sha256_uri(value) == expected
