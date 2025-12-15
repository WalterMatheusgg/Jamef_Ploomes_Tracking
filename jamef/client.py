# jamef/client.py
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import requests

# Se você já tem esse helper no projeto, mantenha.
# Caso não tenha, pode remover e usar só requests direto.
try:
    from utils.http_retry import request_with_retry  # type: ignore
except Exception:  # pragma: no cover
    request_with_retry = None  # fallback

from config import (  # ou from jamef.config import (...)
    JAMEF_AUTH_BASE_URL,
    JAMEF_TRACKING_BASE_URL,
    JAMEF_USERNAME,
    JAMEF_PASSWORD,
    JAMEF_TOKEN_TTL_SECONDS,
    RATE_SLEEP_SECONDS_JAMEF,      # se não existir, defina no config
    TAX_ID_REGISTRATION,           # CNPJ/CPF remetente padrão
)

logger = logging.getLogger("LOGIN JAMEF")


class JamefAuthError(RuntimeError):
    pass


@dataclass
class _TokenCache:
    token: str
    expire_at: datetime  # UTC


class JamefClient:
    """
    Cliente para a API Jamef:
      - Login:    POST {auth_base_url}/login
      - Tracking: GET  {tracking_base_url}/rastreamento
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

        self.auth_base_url = JAMEF_AUTH_BASE_URL.rstrip("/")
        self.tracking_base_url = JAMEF_TRACKING_BASE_URL.rstrip("/")

        self.username = JAMEF_USERNAME
        self.password = JAMEF_PASSWORD

        self.token_ttl_seconds = int(JAMEF_TOKEN_TTL_SECONDS)
        self.rate_sleep_seconds = float(RATE_SLEEP_SECONDS_JAMEF)

        self._cache: Optional[_TokenCache] = None

    # -------------------------
    # Helpers
    # -------------------------
    def _sleep_rate_limit(self) -> None:
        if self.rate_sleep_seconds > 0:
            time.sleep(self.rate_sleep_seconds)

    def _token_valido(self) -> bool:
        if not self._cache:
            return False
        # margem de segurança de 30s para não bater no limite
        return datetime.now(timezone.utc) < (self._cache.expire_at - timedelta(seconds=30))

    def _parse_token_and_ttl(self, data: dict) -> tuple[str, Optional[int]]:
        """
        Suporta:
          - token/access_token/jwt (campos diretos)
          - dado[0].accessToken + expiresIn (formato visto no log)
          - dado.accessToken (caso venha dict)
        Retorna: (token, expires_in_optional)
        """
        token = data.get("token") or data.get("access_token") or data.get("jwt") or data.get("accessToken")
        expires_in: Optional[int] = None

        if not token:
            dado = data.get("dado") or data.get("Dado")
            if isinstance(dado, list) and dado:
                token = dado[0].get("accessToken") or dado[0].get("token")
                ei = dado[0].get("expiresIn")
                if isinstance(ei, int) and ei > 0:
                    expires_in = ei
            elif isinstance(dado, dict):
                token = dado.get("accessToken") or dado.get("token")
                ei = dado.get("expiresIn")
                if isinstance(ei, int) and ei > 0:
                    expires_in = ei

        if not token:
            raise JamefAuthError(f"Login Jamef OK, mas token não encontrado. Resposta: {data}")

        return token, expires_in

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Usa request_with_retry se disponível; senão usa requests direto.
        """
        if request_with_retry:
            return request_with_retry(method, url, timeout=self.timeout, **kwargs)
        return self.session.request(method, url, timeout=self.timeout, **kwargs)

    # -------------------------
    # AUTH
    # -------------------------
    def _obter_token(self) -> str:
        if self._token_valido():
            return self._cache.token  # type: ignore[union-attr]

        self._sleep_rate_limit()

        url = f"{self.auth_base_url}/login"
        payload = {"username": self.username, "password": self.password}

        logger.info("Realizando login na Jamef... (%s)", url)

        try:
            r = self._request("POST", url, json=payload)
        except Exception as e:
            raise JamefAuthError(f"Falha de rede no login Jamef: {e}") from e

        # parse JSON com fallback
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}

        if r.status_code != 200:
            msg = data.get("mensagem") or data.get("message") or "Falha no login"
            raise JamefAuthError(f"Login Jamef retornou HTTP {r.status_code}: {msg}")

        token, expires_in = self._parse_token_and_ttl(data)

        # TTL: prioriza expiresIn se vier, senão usa config
        ttl = int(expires_in) if isinstance(expires_in, int) and expires_in > 0 else self.token_ttl_seconds
        expire_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        self._cache = _TokenCache(token=token, expire_at=expire_at)
        logger.info("Login CONCLUIDO. Token em cache (TTL=%ss).", ttl)

        return token

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._obter_token()}",
        }

    # -------------------------
    # TRACKING
    # -------------------------
    def rastreamento(
        self,
        documentoRemetente: str,
        numeroNotaFiscal: str,
        serieNotaFiscal: Optional[str] = None,
        documentoDestinatario: Optional[str] = None,
    ) -> dict[str, Any]:
        if not documentoRemetente:
            raise ValueError("documentoRemetente não informado.")
        if not numeroNotaFiscal:
            raise ValueError("numeroNotaFiscal não informado.")

        params: dict[str, Any] = {
            "documentoRemetente": documentoRemetente,
            "numeroNotaFiscal": numeroNotaFiscal,
        }
        if serieNotaFiscal:
            params["serieNotaFiscal"] = serieNotaFiscal
        if documentoDestinatario:
            params["documentoDestinatario"] = documentoDestinatario

        url = f"{self.tracking_base_url}/rastreamento"

        self._sleep_rate_limit()
        r = self._request("GET", url, headers=self._headers(), params=params)

        # retry simples para 429 (mantém o comportamento do 2º código)
        if r.status_code == 429:
            logger.warning("429 Too Many Requests na Jamef. Aguardando e tentando novamente...")
            time.sleep(self.rate_sleep_seconds * 2 if self.rate_sleep_seconds > 0 else 2)
            r = self._request("GET", url, headers=self._headers(), params=params)

        try:
            data = r.json()
        except Exception:
            data = {"situacao": 0, "mensagem": "Resposta não-JSON da API", "raw": r.text}

        if r.status_code != 200:
            msg = data.get("mensagem") or data.get("message") or data
            id_corr = data.get("idCorrelacao") if isinstance(data, dict) else None
            raise RuntimeError(f"Erro Jamef HTTP {r.status_code}: {msg} | idCorrelacao={id_corr}")

        return data

    def get_tracking_by_invoice(self, invoice_number: str) -> dict[str, Any]:
        """
        Compatível com o 1º código: usa TAX_ID_REGISTRATION como documentoRemetente
        e consulta por numeroNotaFiscal.
        """
        return self.rastreamento(
            documentoRemetente=TAX_ID_REGISTRATION,
            numeroNotaFiscal=invoice_number,
        )
