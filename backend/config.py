import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./coglink.db")
    
    # 涂鸦配置（稍后填）
    TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID", "8cfyxj3aqstscgtwtqsw")
    TUYA_ACCESS_SECRET = os.getenv("TUYA_ACCESS_SECRET", "618cbf281c9f48d1aae1b7bd94aca8f2")
    TUYA_API_ENDPOINT = os.getenv("TUYA_API_ENDPOINT", "https://openapi.tuyacn.com")
    
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))