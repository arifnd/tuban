from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORAGE_", env_file=".env", extra="ignore")

    BACKEND: Literal["local", "s3"] = "local"
    # Authoritative default for the upload size cap. Runtime settings
    # (src/settings/service.defaults) seed from this value and may override it.
    UPLOAD_MAX_SIZE: int = 128 * 1024 * 1024
    LOCAL_DIR: str = ""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = ""
    AWS_ENDPOINT_URL: str = ""
    AWS_S3_BUCKET: str = ""


@lru_cache
def get_storage_settings() -> StorageConfig:
    return StorageConfig()
