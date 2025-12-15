# utils/http_retry.py
import time
import logging
import requests

log = logging.getLogger("http-retry")

def request_with_retry(method, url, **kwargs):
    """
    Executa requests com retry para 429 e 5xx.
    Respeita Retry-After se existir.
    """
    max_attempts = int(kwargs.pop("max_attempts", 4))
    timeout = kwargs.pop("timeout", 10)
    backoff = 1.0
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            status = resp.status_code

            # sucesso
            if status < 400:
                return resp

            # retry para 429 ou 5xx
            if status == 429 or 500 <= status < 600:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        wait = backoff
                else:
                    wait = backoff

                log.warning(f"{status} em {url} — tentativa {attempt}/{max_attempts}, aguardando {wait}s...")
                time.sleep(wait)
                backoff = min(backoff * 2, 16)
                continue

            # outros erros (400, 401, 422 etc) -> não retry
            resp.raise_for_status()

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            log.warning(f"Erro de conexão em {url} — tentativa {attempt}/{max_attempts}: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 16)
            continue

        except requests.HTTPError as e:
            # erro HTTP não elegível para retry (já demos raise_for_status)
            raise

    # se esgotar tentativas
    if last_exc:
        raise last_exc
    raise requests.exceptions.RequestException(f"Falha ao acessar {url} após {max_attempts} tentativas")
