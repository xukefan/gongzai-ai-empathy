import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./coglink.db")

    # 密钥只能来自本地 .env 或部署环境，禁止提供仓库内默认值。
    TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
    TUYA_ACCESS_SECRET = os.getenv("TUYA_ACCESS_SECRET")
    TUYA_API_ENDPOINT = os.getenv("TUYA_API_ENDPOINT", "https://openapi.tuyacn.com")

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
