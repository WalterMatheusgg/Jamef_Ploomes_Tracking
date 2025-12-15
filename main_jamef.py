# main_jamef.py
import csv
import os
from datetime import datetime
import logging
from time import sleep
from typing import List

from text_cleaner import limpar_status_rastreamento
from typing import List, Optional
from logging_config import setup_logging
from jamef import JamefClient
from ploomes import PloomesClient
from utils.helpers import compute_estimated_delivery_datetime
from config import (
    TAX_ID_REGISTRATION,
    PLOOMES_KEY,
    STATUS_DESCRIPTION_FIELD_KEY,
    ESTIMATED_DELIVERY_DATE_FIELD_KEY,
    DELIVERY_DATE_UPDATED_FIELD_KEY,
    DELIVERY_STATUS_FIELD_KEY,
    ORDER_ID_FIELD_KEY,
    TRANSPORTER_FIELD_KEY,
    TRANSPORTER_VALUE_JAMEF,
    PIPELINE_ID,
    STAGE_IDS,
    HOLIDAYS_BR,
    RATE_SLEEP_SECONDS_JAMEF,
    DRY_RUN,
    LOG_FILE_JAMEF,
    AUDIT_DIR_JAMEF,
)

setup_logging(LOG_FILE_JAMEF)
log = logging.getLogger("JAMEF LTDA")


def to_date_only_iso(value):
    """
    Converte '2024-04-05' ou '2024-04-05T10:20:00[Z]'
    em '2024-04-05T00:00:00' (string), ou None se não der pra parsear.
    """
    if not value:
        return None
    s = str(value).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.date().isoformat() + "T00:00:00"
    except Exception:
        return None


# ---------------- utils ----------------
def build_filter_for_pipeline_stages(pipeline_id: int, stage_ids: List[int]) -> str:
    stage_expr = " or ".join([f"(StageId eq {sid})" for sid in stage_ids])
    return f"(PipelineId eq {pipeline_id}) and ({stage_expr})"


def get_other_property_value(other_props: List[dict], field_key: str):
    for p in other_props or []:
        if p.get("FieldKey") == field_key:
            return (
                p.get("ContactValueName")
                or p.get("ObjectValueName")
                or p.get("EnumValueName")
                or p.get("StringValue")
                or p.get("DateTimeValue")
                or (
                    str(p.get("IntegerValue"))
                    if p.get("IntegerValue") is not None
                    else ""
                )
                or ""
            )
    return None


def is_jamef(name: str) -> bool:
    return (name or "").strip().casefold().startswith("jamef")


def _extract_first_rastreamento_blob(data: dict) -> dict:
    """
    Normaliza o JSON de rastreamento da Jamef, pegando o primeiro bloco:

    {
      "situacao": 200,
      "mensagem": "...",
      "dado": [
        {
          "rastreamento": [
            {
              "frete": {...},
              "eventosRastreio": [...]
            }
          ]
        }
      ]
    }
    """
    if not isinstance(data, dict):
        return {}
    dado = data.get("dado") or data.get("Dado")
    if isinstance(dado, list) and dado:
        bloco = dado[0]
    elif isinstance(dado, dict):
        bloco = dado
    else:
        bloco = data

    rast = bloco.get("rastreamento") or bloco.get("Rastreamento")
    if isinstance(rast, list) and rast:
        return rast[0]
    if isinstance(rast, dict):
        return rast
    return bloco


def _norm(s: str) -> str:
    return (s or "").strip().upper()


def _parse_dt(iso: str):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None


def _sort_eventos(eventos: list) -> list:
    """
    Ordena eventos por data/hora (do mais antigo para o mais recente).
    Eventos sem data vão para o fim.
    """
    def key(e):
        dt = _parse_dt((e or {}).get("data") or (e or {}).get("Data") or "")
        return (dt is None, dt or datetime.min)

    return sorted(eventos or [], key=key)


def _infer_stage(eventos_ordenados: list) -> str:
    """
    Infere um estágio canônico a partir do último status textual da Jamef.
    """
    if not eventos_ordenados:
        return "SEM_EVENTOS"

    last = eventos_ordenados[-1]
    st = _norm(last.get("status") or last.get("Status") or "")

    delivered_kw = [
    "ENTREGUE",
    "ENTREGA EFETUADA",
    "FINALIZADA",
    "MERCADORIA ENTREGUE",
    "ENTREGA REALIZADA",
    "ENTREGA REALIZADA NORMALMENTE",
]
    if any(k in st for k in delivered_kw):
        return "ENTREGUE"

    out_kw = ["SAIU PARA ENTREGA",
            "EM ROTA DE ENTREGA",
            "ROTA DE ENTREGA",
            "EM ENTREGA"
            ]
    if any(k in st for k in out_kw):
        return "SAIU_PARA_ENTREGA"

    exc_kw = [
        "DEVOLU",
        "RECUS",
        "AVARIA",
        "EXTRAV",
        "SINISTR",
        "RETIDO",
        "PENDEN",
        "CANCEL",
        "NÃO LOCALIZ",
        "NAO LOCALIZ",
        "ENDERE",
    ]
    if any(k in st for k in exc_kw):
        return "EXCECAO"

    transit_kw = [
        "TRANSFER",
        "TRÂNSITO",
        "TRANSITO",
        "TRIAGEM",
        "COLETA",
        "CHEGADA",
        "SAIDA",
        "SAÍDA",
        "RECEBID",
        "EM UNIDADE",
        "ROTEIR",
    ]
    if any(k in st for k in transit_kw):
        return "EM_TRANSFERENCIA"

    started_kw = [
        "DOCUMENTO EMITIDO",
        "CONHECIMENTO EMITIDO",
        "REGISTRADO",
        "PEDIDO INICIADO",
    ]
    if any(k in st for k in started_kw):
        return "INICIADO"

    return "INICIADO"

def _find_delivered_event_date(eventos_ordenados: list) -> Optional[str]:
    """
    Busca a data da entrega a partir do evento mais recente que indique "entregue".
    Retorna a data em ISO (YYYY-MM-DDT00:00:00) quando possível.
    """
    if not eventos_ordenados:
        return None

    delivered_kw = [
        "ENTREGUE",
        "ENTREGA EFETUADA",
        "FINALIZADA",
        "MERCADORIA ENTREGUE",
        "ENTREGA REALIZADA",
        "ENTREGA REALIZADA NORMALMENTE",
    ]

    for e in reversed(eventos_ordenados or []):  # do mais recente pro mais antigo
        st = _norm((e or {}).get("status") or (e or {}).get("Status") or "")
        if any(k in st for k in delivered_kw):
            raw_dt = ((e or {}).get("data") or (e or {}).get("Data") or "").strip()
            if raw_dt:
                return to_date_only_iso(raw_dt) or raw_dt

    return None



def extract_tracking_info_from_jamef(data: dict):
    """
    Retorna:
      - descricao: texto rico -> "<ESTADO_INFERIDO> | <último status> | <data/hora último evento>"
      - estimated_delivery_iso: frete.previsaoEntrega (normalizado p/ 'YYYY-MM-DDT00:00:00')
                                ou calculada por emissao+prazos
      - delivered_iso: data de entrega se detectada (via find_delivered_event_date)
      - clean_status: status "curto" e limpo para campo próprio no Ploomes
    """
    rast = _extract_first_rastreamento_blob(data)

    eventos = rast.get("eventosRastreio") or rast.get("EventosRastreio") or []
    eventos = _sort_eventos(eventos)

    frete = rast.get("frete") or rast.get("Frete") or {}

    # Data real de entrega (se houver evento de entregue)
    delivered_iso = None
    if eventos:
        try:
            delivered_iso = _find_delivered_event_date(eventos)
        except Exception:
            delivered_iso = None


    # Previsão de entrega vinda da Jamef
    estimated_delivery_iso = frete.get("previsaoEntrega") or frete.get("PrevisaoEntrega")

    # Fallback: se não vier previsão explícita, calcula pela dataEmissao + prazoEntrega
    if not estimated_delivery_iso:
        emission_iso = rast.get("dataEmissao") or rast.get("DataEmissao")
        expected_days = rast.get("prazoEntrega") or rast.get("PrazoEntrega")
        if emission_iso and expected_days is not None:
            try:
                estimated_delivery_iso = compute_estimated_delivery_datetime(
                    emission_iso, int(expected_days), HOLIDAYS_BR
                )
            except Exception as e:
                log.warning(
                    "Falha ao calcular previsão (emission=%s, days=%s): %s",
                    emission_iso,
                    expected_days,
                    e,
                )

    # Normaliza previsão para 'YYYY-MM-DDT00:00:00', se possível
    if estimated_delivery_iso:
        normalized = to_date_only_iso(estimated_delivery_iso)
        if normalized:
            estimated_delivery_iso = normalized

    stage = _infer_stage(eventos)

    if not eventos:
        descricao = "SEM_EVENTOS | Sem eventos no rastreio"
        clean_status = limpar_status_rastreamento(descricao)
        return descricao, estimated_delivery_iso, delivered_iso, clean_status

    last = eventos[-1]
    last_status = (last.get("status") or last.get("Status") or "").strip()
    last_data = (last.get("data") or last.get("Data") or "").strip()

    descricao = f"{stage} | {last_status} | {last_data}"
    clean_status = limpar_status_rastreamento(last_status)

    return descricao, estimated_delivery_iso, delivered_iso, clean_status


# ---------------- pipeline ----------------
def process_one_deal(
    jamef: JamefClient,
    ploomes: PloomesClient,
    deal: dict,
    audit_writer: csv.writer,
):
    deal_id = deal["Id"]

    # 1) OtherProperties
    other_props = ploomes.get_otherprops_resilient(
        deal_id, prefer_field_key=TRANSPORTER_FIELD_KEY
    )
    if not other_props:
        log.warning(f"[{deal_id}] Não foi possível obter OtherProperties — pulando.")
        audit_writer.writerow(
            [deal_id, deal.get("StageId"), deal.get("Title"), "", "", "", "sem_otherprops"]
        )
        return

    # 2) Transportadora (tem que ser JAMEF)
    transporter_value = get_other_property_value(other_props, TRANSPORTER_FIELD_KEY)
    if not is_jamef(transporter_value):
        log.info(f"[{deal_id}] Transportadora='{transporter_value}' não é JAMEF — pulando.")
        audit_writer.writerow(
            [
                deal_id,
                deal.get("StageId"),
                deal.get("Title"),
                transporter_value,
                "",
                "",
                "nao_jamef",
            ]
        )
        return

    # 3) Nº nota fiscal
    order_id = get_other_property_value(other_props, ORDER_ID_FIELD_KEY)
    if not order_id:
        log.info(f"[{deal_id}] Sem Nº nota fiscal — pulando.")
        audit_writer.writerow(
            [
                deal_id,
                deal.get("StageId"),
                deal.get("Title"),
                transporter_value,
                "",
                "",
                "sem_nf",
            ]
        )
        return

    # 4) Jamef (rastreamento)
    data = jamef.get_tracking_by_invoice(str(order_id))

    if not data:
        log.info(
            f"[{deal_id}] Jamef sem rastreio para NF={order_id} — pulando."
        )
        audit_writer.writerow(
            [
                deal_id,
                deal.get("StageId"),
                deal.get("Title"),
                transporter_value,
                "",
                "",
                "sem_rastreio",
            ]
        )
        return

    descricao, estimated_delivery_iso, delivered_iso, clean_status = (
        extract_tracking_info_from_jamef(data)
    )

    if not descricao:
        log.info(f"[{deal_id}] Jamef sem eventos — pulando.")
        audit_writer.writerow(
            [
                deal_id,
                deal.get("StageId"),
                deal.get("Title"),
                transporter_value,
                "",
                "",
                "sem_eventos",
            ]
        )
        return

        # 5) Update Ploomes (ESTILO RODONAVES)
    if DRY_RUN:
        log.info(
            f"[DRY_RUN] {deal_id} status='{descricao[:120]}', "
            f"previsao='{estimated_delivery_iso}', entrega='{delivered_iso}'"
        )
        return

    # --------- igual ao Rodonaves: só datas adicionais ----------
    additional_datetime_updates = []
    if delivered_iso:
        additional_datetime_updates.append((DELIVERY_DATE_UPDATED_FIELD_KEY, delivered_iso))

    # --------- igual ao Rodonaves: descricao "pura" ----------
    # Rodonaves manda apenas o texto do último evento no campo de status.
    # Aqui, em vez de "stage | status | data", mandamos só o status do último evento.
    last_status_only = clean_status or ""

    ploomes.update_status(
        deal_id=deal_id,
        field_key=STATUS_DESCRIPTION_FIELD_KEY,
        descricao=last_status_only,
        date_field_key=ESTIMATED_DELIVERY_DATE_FIELD_KEY,
        delivery_date=estimated_delivery_iso,
        additional_datetime_updates=additional_datetime_updates,
    )

# 6) Auditoria
    audit_writer.writerow(
        [
            deal_id,
            deal.get("StageId"),
            deal.get("Title"),
            transporter_value,
            estimated_delivery_iso or "",
            delivered_iso or "",
            "ok",
            order_id,
            f"'{descricao[:120]}'",
        ]
    )

    log.info(
        f"[{deal_id}] OK — '{descricao[:120]}' | "
        f"previsao='{estimated_delivery_iso}' | entrega='{delivered_iso}'"
    )


def main():
    jamef = JamefClient()
    ploomes = PloomesClient(PLOOMES_KEY)

    filter_odata = build_filter_for_pipeline_stages(PIPELINE_ID, STAGE_IDS)
    log.info(f"Filtro: {filter_odata}")
    log.info(f"Pipeline={PIPELINE_ID} | Stages={STAGE_IDS} | DRY_RUN={DRY_RUN}")

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    audit_path = os.path.join(AUDIT_DIR_JAMEF, f"audit_jamef_{ts}.csv")

    with open(audit_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "deal id",
                "stage id",
                "title",
                "transportadora",
                "previsao calculada",
                "entrega real",
                "status execucao",
                "Nota Fiscal",
                "Status da Entrega",
            ]
        )

        count = 0
        for deal in ploomes.iter_deals(filter_odata, top=50):
            try:
                process_one_deal(jamef, ploomes, deal, writer)
                count += 1
            except Exception as e:
                log.warning(f"[{deal.get('Id')}] ERRO — {e}")
                writer.writerow(
                    [
                        deal.get("Id"),
                        deal.get("StageId"),
                        deal.get("Title"),
                        "",
                        "",
                        "",
                        f"erro:{type(e).__name__}",
                    ]
                )
            finally:
                sleep(RATE_SLEEP_SECONDS_JAMEF)

    log.info(f"Concluído. Negócios percorridos: {count} | CSV: {audit_path}")


if __name__ == "__main__":
    main()
