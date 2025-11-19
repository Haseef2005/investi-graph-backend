from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # โหลดไฟล์ .env
    # (ผมแถม extra="ignore" ให้ครับ เผื่อใน .env มีตัวแปรเกิน มันจะได้ไม่ Error)
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" 
    )

    # --- 1. Project Settings ---
    PROJECT_NAME: str = "Investi-Graph"
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- 2. Database Settings (PostgreSQL) ---
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_URL: str

    # --- 3. LLM Settings ---
    LLM_PROVIDER: str = "groq"
    LLM_API_KEY: str

    # --- 4. (เพิ่มใหม่!) Neo4j Settings ---
    NEO4J_URI: str = "bolt://localhost:7687" # ใส่ Default ไว้กันลืม
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str

# สร้าง instance เพื่อให้ import ไปใช้ที่อื่นได้
settings = Settings()