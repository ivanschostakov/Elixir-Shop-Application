from logger import setup_logging
from src.app.main import run_app


async def main():
    await run_app()


if __name__ == "__main__":
    setup_logging()

    import asyncio

    try: asyncio.run(main())
    except KeyboardInterrupt: pass
