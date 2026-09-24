from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORAGE_", env_file=".env", extra="ignore")

    BACKEND: str = "local"
    UPLOAD_MAX_SIZE: int = 20 * 1024 * 1024

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = ""
    AWS_ENDPOINT_URL: str = ""
    AWS_S3_BUCKET: str = ""


storage_settings = StorageConfig()
