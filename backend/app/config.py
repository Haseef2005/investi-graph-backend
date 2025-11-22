from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Load .env file
    # extra="ignore" so it doesn't error if there are extra variables in .env
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

    # --- 4. Neo4j Settings ---
    NEO4J_URI: str = "bolt://localhost:7687" # Default value
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str

    SEC_API_EMAIL: str = "phuminunsk141@gamail.com"

# Create instance to import elsewhere
settings = Settings()