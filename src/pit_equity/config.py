import os

from dotenv import load_dotenv


def sec_user_agent() -> str:
    load_dotenv()
    value = os.getenv("SEC_USER_AGENT", "").strip()
    if not value:
        raise RuntimeError("SEC_USER_AGENT is missing from the local environment")
    return value
