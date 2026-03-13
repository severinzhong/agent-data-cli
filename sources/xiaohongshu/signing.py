from __future__ import annotations

import base64
import hashlib
import json
import time
from urllib.parse import urlencode

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from xhshow import CryptoConfig, SessionManager, Xhshow

from .constants import APP_ID, PLATFORM, SDK_VERSION, USER_AGENT


_config = CryptoConfig().with_overrides(
    PUBLIC_USERAGENT=USER_AGENT,
    SIGNATURE_DATA_TEMPLATE={
        "x0": SDK_VERSION,
        "x1": APP_ID,
        "x2": PLATFORM,
        "x3": "",
        "x4": "",
    },
    SIGNATURE_XSCOMMON_TEMPLATE={
        "s0": 5,
        "s1": "",
        "x0": "1",
        "x1": SDK_VERSION,
        "x2": PLATFORM,
        "x3": APP_ID,
        "x4": "4.86.0",
        "x5": "",
        "x6": "",
        "x7": "",
        "x8": "",
        "x9": -596800761,
        "x10": 0,
        "x11": "normal",
    },
)
_xhshow = Xhshow(_config)
_session = SessionManager(_config)

_AES_KEY = b"7cc4adla5ay0701v"
_AES_IV = b"4uzjr7mbsibcaldp"


def sign_main_api(
    method: str,
    uri: str,
    cookies: dict[str, str],
    *,
    params: dict[str, str | int | list[str]] | None = None,
    payload: dict | None = None,
    timestamp: float | None = None,
) -> dict[str, str]:
    if method.upper() == "GET":
        return _xhshow.sign_headers_get(uri, cookies, params=params, timestamp=timestamp, session=_session)
    return _xhshow.sign_headers_post(uri, cookies, payload=payload, timestamp=timestamp, session=_session)


def build_get_uri(uri: str, params: dict[str, str | int | list[str]] | None = None) -> str:
    if not params:
        return uri
    return f"{uri}?{urlencode(params, doseq=True)}"


def sign_creator(api: str, data: dict | None, a1: str) -> dict[str, str]:
    content = api
    if data is not None:
        content += json.dumps(data, separators=(",", ":"))

    x1 = hashlib.md5(content.encode("utf-8")).hexdigest()
    x2 = "0|0|0|1|0|0|1|0|0|0|1|0|0|0|0|1|0|0|0"
    x4 = int(time.time() * 1000)

    plaintext = f"x1={x1};x2={x2};x3={a1};x4={x4};"
    payload = _aes_encrypt(base64.b64encode(plaintext.encode("utf-8")).decode("utf-8"))
    envelope = {
        "signSvn": "56",
        "signType": "x2",
        "appId": "ugc",
        "signVersion": "1",
        "payload": payload,
    }
    xs = "XYW_" + base64.b64encode(json.dumps(envelope, separators=(",", ":")).encode("utf-8")).decode("utf-8")
    return {
        "x-s": xs,
        "x-t": str(x4),
    }


def _aes_encrypt(data: str) -> str:
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    padded = pad(data.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return encrypted.hex()

