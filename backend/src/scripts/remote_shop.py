import os


def remote_shop_database_url() -> str:
    user = os.environ["SHOP_POSTGRES_USER"]
    password = os.environ["SHOP_POSTGRES_PASSWORD"]
    host = os.environ["SHOP_POSTGRES_HOST"]
    port = os.environ.get("SHOP_POSTGRES_PORT", "5432")
    database = os.environ["SHOP_POSTGRES_DB"]
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
