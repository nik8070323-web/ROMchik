import os
from pathlib import Path
from dotenv import load_dotenv


def load_environment():
    explicit = os.getenv("ENV_FILE")
    if explicit:
        load_dotenv(explicit)
    else:
        for path in (Path("/home/container/.env"), Path(__file__).resolve().parents[1] / ".env", Path(__file__).resolve().parents[2] / ".env"):
            load_dotenv(path, override=False)


load_environment()
