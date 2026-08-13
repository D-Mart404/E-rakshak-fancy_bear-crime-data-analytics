from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://127.0.0.1:27017"
    MONGO_DB: str = "erakshak"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
