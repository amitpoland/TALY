from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Multi-Currency Brokerage Clearing & Commission Ledger"
    database_url: str = "sqlite:///./brokerage_ledger.sqlite3"

    model_config = SettingsConfigDict(env_prefix="LEDGER_", env_file=".env", extra="ignore")


settings = Settings()

