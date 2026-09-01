import requests
import hashlib
import hmac
import json
import time
import uuid
from config import Config

class TuyaClient:
    def __init__(self):
        self.access_id = Config.TUYA_ACCESS_ID
        self.access_secret = Config.TUYA_ACCESS_SECRET
        self.endpoint = Config.TUYA_API_ENDPOINT
        self.token = None
        self.token_expire = 0
    
    def _get_sign(self, method, path, body="", access_token=""):
        t = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        string_to_sign = f"{method}\n{content_hash}\n\n{path}"
        sign_payload = self.access_id + access_token + t + nonce + string_to_sign
        sign = hmac.new(
            self.access_secret.encode(),
            sign_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest().upper()
        return sign, t, nonce

    def _require_credentials(self):
        if not self.access_id or not self.access_secret:
            raise RuntimeError("Tuya credentials are not configured")
    
    def _get_token(self):
        if self.token and time.time() < self.token_expire:
            return self.token

        self._require_credentials()
        path = "/v1.0/token?grant_type=1"
        sign, t, nonce = self._get_sign("GET", path)
        
        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "t": t,
            "nonce": nonce,
            "sign_method": "SHA256"
        }
        
        response = requests.get(self.endpoint + path, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            self.token = data["result"]["access_token"]
            self.token_expire = time.time() + data["result"]["expire_time"] - 60
            return self.token
        else:
            raise Exception(f"涂鸦获取Token失败: {data}")
    
    def send_command(self, device_id, code, value):
        token = self._get_token()
        path = f"/v1.0/devices/{device_id}/commands"

        commands = [{
            "code": code,
            "value": value
        }]
        body = json.dumps({"commands": commands}, separators=(",", ":"))
        
        sign, t, nonce = self._get_sign("POST", path, body, token)
        headers = {
            "client_id": self.access_id,
            "access_token": token,
            "sign": sign,
            "t": t,
            "nonce": nonce,
            "sign_method": "SHA256",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            self.endpoint + path,
            headers=headers,
            data=body,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            return True
        else:
            raise Exception(f"涂鸦下发失败: {result}")
