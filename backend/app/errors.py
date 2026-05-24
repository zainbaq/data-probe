from typing import Any


def error_payload(code: str, message: str, details: Any = None) -> dict:
    payload = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return payload
