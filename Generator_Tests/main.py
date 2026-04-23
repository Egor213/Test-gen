import asyncio

from src.app.app import main

def main_sync():
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
