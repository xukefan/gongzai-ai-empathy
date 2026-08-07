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

    def _require_credentials(self):
        if not self.access_id or not self.access_secret:
            raise RuntimeError(
                "TUYA_ACCESS_ID and TUYA_ACCESS_SECRET must be provided via environment variables"
            )
    
    def _get_sign(self, method, path, body=""):
        t = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        string_to_sign = method + "\n" + hashlib.sha256(body.encode()).hexdigest() + "\n" + t + "\n" + nonce + "\n"
        sign = hmac.new(
            self.access_secret.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest().upper()
        return sign, t, nonce
    
    def _get_token(self):
        self._require_credentials()
        if self.token and time.time() < self.token_expire:
            return self.token
        
        path = "/v1.0/token?grant_type=1"
        sign, t, nonce = self._get_sign("GET", path)
        
        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "t": t,
            "nonce": nonce,
            "sign_method": "SHA256"
        }
        
        response = requests.get(self.endpoint + path, headers=headers)
        data = response.json()
        
        if data.get("success"):
            self.token = data["result"]["access_token"]
            self.token_expire = time.time() + data["result"]["expire_time"] - 60
            return self.token
        else:
            raise Exception(f"涂鸦获取Token失败: {data}")
    
    def send_command(self, device_id, dp_id, value):
        token = self._get_token()
        path = f"/v1.0/devices/{device_id}/commands"
        
        commands = [{
            "code": f"dp_{dp_id}",
            "value": value
        }]
        body = json.dumps({"commands": commands})
        
        sign, t, nonce = self._get_sign("POST", path, body)
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
            data=body
        )
        
        result = response.json()
        if result.get("success"):
            return True
        else:
            raise Exception(f"涂鸦下发失败: {result}")
