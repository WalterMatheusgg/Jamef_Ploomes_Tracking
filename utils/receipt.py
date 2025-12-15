import requests
import base64
import time
from config import RATE_SLEEP_SECONDS_JAMEF

def baixar_comprovante_base64(url: str) -> str:
    time.sleep(RATE_SLEEP_SECONDS_JAMEF)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")
