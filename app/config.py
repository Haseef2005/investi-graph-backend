from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # โหลดไฟล์ .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ตัวแปรที่เรากำหนดใน .env
    PROJECT_NAME: str = "Investi-Graph"
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_HOST: str
    DATABASE_PORT: int

    DATABASE_URL: str

# สร้าง instance เพื่อให้ import ไปใช้ที่อื่นได้
settings = Settings()