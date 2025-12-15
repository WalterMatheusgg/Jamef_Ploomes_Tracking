# ploomes/client.py
import requests
from typing import List, Tuple, Optional

# Wrapper de requests com retry e backoff para 429/5xx
from utils.http_retry import request_with_retry


class PloomesClient:
    """
    Cliente de integração com a API do Ploomes.
    Responsável por:
      - Listar negócios (Deals) com paginação
      - Ler OtherProperties com diferentes estratégias (fallbacks)
      - Atualizar campos (OtherProperties) de um negócio
    """
    def __init__(self, user_key: str):
        self.base_url = "https://api2.ploomes.com"
        self.headers = {"User-Key": user_key, "Content-Type": "application/json"}

    def iter_deals(self, filter_odata: str, top: int = 50):
        skip = 0
        while True:
            params = {
                "$filter": filter_odata,
                "$select": "Id,Title,StageId,PipelineId",
                "$top": top,
                "$skip": skip
            }
            resp = request_with_retry("GET", f"{self.base_url}/Deals", headers=self.headers, params=params)
            data = resp.json()
            items = data.get("value", [])

            if not items:
                break

            for item in items:
                yield item

            skip += top

    # ---------------- Estratégias internas para ler OtherProperties ----------------
    def _get_otherprops_via_deals_expand_by_filter(self, deal_id: int) -> list[dict]:
        params = {
            "$top": 1,
            "$skip": 0,
            "$select": "*",
            "$expand": "OtherProperties",
            "$filter": f"Id eq {deal_id}",
            "$orderby": "Id desc",
        }
        resp = request_with_retry("GET", f"{self.base_url}/Deals", headers=self.headers, params=params)
        data = resp.json()
        values = data.get("value") or []
        if not values:
            return []
        return values[0].get("OtherProperties") or []

    def _get_otherprops_via_deal_expand(self, deal_id: int) -> list[dict]:
        params = {
            "$expand": "OtherProperties($select=FieldKey,StringValue,DateTimeValue,ObjectValueName,EnumValueName,IntegerValue,ContactValueName)"
        }
        resp = request_with_retry("GET", f"{self.base_url}/Deals({deal_id})", headers=self.headers, params=params)

        value = (resp.json().get("value") or [None])[0]
        if not value:
            return []
        return value.get("OtherProperties") or []

    def _resolve_field_id(self, field_key: str) -> int:
        params = {"$filter": f"Key eq '{field_key}'", "$select": "Id,Key"}
        resp = request_with_retry("GET", f"{self.base_url}/Fields", headers=self.headers, params=params)
        items = resp.json().get("value", [])
        if not items or not isinstance(items[0].get("Id"), int):
            raise RuntimeError(f"FieldKey '{field_key}' não encontrado em /Fields.")
        return items[0]["Id"]

    def _get_otherprops_by_fieldid(self, deal_id: int, field_id: int) -> list[dict]:
        params = {
            "$filter": f"FieldId eq {field_id}",
            "$select": "FieldId,FieldKey,ContactValueName,ObjectValueName,EnumValueName,StringValue,DateTimeValue,IntegerValue",
            "$top": 50,
        }
        url = f"{self.base_url}/Deals({deal_id})/OtherProperties"
        resp = request_with_retry("GET", url, headers=self.headers, params=params)
        return resp.json().get("value", []) or []

    # ---------------- API pública para obter OtherProperties com fallbacks ----------------
    def get_otherprops_resilient(self, deal_id: int, prefer_field_key: Optional[str] = None) -> list[dict]:
        try:
            props = self._get_otherprops_via_deals_expand_by_filter(deal_id)
            if props:
                return props
        except requests.HTTPError:
            pass

        try:
            props = self._get_otherprops_via_deal_expand(deal_id)
            if props:
                return props
        except requests.HTTPError:
            pass

        if prefer_field_key:
            try:
                fid = self._resolve_field_id(prefer_field_key)
                props = self._get_otherprops_by_fieldid(deal_id, fid)
                if props:
                    return props
            except requests.HTTPError:
                pass

        return []

    # ---------------- Atualização de status no Ploomes ----------------
    def update_status(
        self,
        deal_id: int,
        field_key: str,
        descricao: str,
        date_field_key: Optional[str] = None,
        delivery_date: Optional[str] = None,
        additional_datetime_updates: Optional[List[Tuple[str, str]]] = None,
        additional_string_updates: Optional[List[Tuple[str, str]]] = None,
    ):
        """
        Atualiza o status do negócio no Ploomes via OtherProperties.

        - Sempre atualiza o campo de descrição (StringValue).
        - Previsão de Entrega (date_field_key) só grava se ainda estiver vazio.
        - additional_datetime_updates: sempre grava DateTimeValue (FieldKey, ISO datetime).
        - additional_string_updates: sempre grava StringValue (FieldKey, valor string).
          (Aqui entra: transportadora, nº NF, status canônico, base64 se você tiver campo string pra isso, etc.)
        """

        payload = {
            "OtherProperties": [
                {"FieldKey": field_key, "StringValue": descricao or ""}
            ]
        }

        # Previsão de Entrega: só grava se ainda não houver valor no campo
        if date_field_key and delivery_date:
            campos = self.get_otherprops_resilient(deal_id, prefer_field_key=date_field_key)
            previsao_existente = next(
                (c for c in campos if c.get("FieldKey") == date_field_key and c.get("DateTimeValue")),
                None
            )
            if not previsao_existente:
                payload["OtherProperties"].append({"FieldKey": date_field_key, "DateTimeValue": delivery_date})

        # Campos adicionais de data/hora (sempre grava)
        for fk, dt_iso in (additional_datetime_updates or []):
            if fk and dt_iso:
                payload["OtherProperties"].append({"FieldKey": fk, "DateTimeValue": dt_iso})

        # Campos adicionais string (sempre grava)
        for fk, val in (additional_string_updates or []):
            if fk and val is not None:
                payload["OtherProperties"].append({"FieldKey": fk, "StringValue": str(val)})

        resp = request_with_retry("PATCH", f"{self.base_url}/Deals({deal_id})", headers=self.headers, json=payload)
        return resp.json()
