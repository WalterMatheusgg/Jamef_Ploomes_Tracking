import datetime
from datetime import datetime, timedelta, date
from typing import Iterable, Optional, Set, List, Dict, Any

def parse_iso_datetime(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str)

def add_business_days(start: datetime, days: int, holidays: Optional[Iterable[date]] = None) -> datetime:
    if days is None or days <= 0:
        return start
    holidays_set: Set[date] = set(holidays or [])
    current = start
    added = 0
    one_day = timedelta(days=1)
    while added < days:
        current = current + one_day
        if current.weekday() < 5 and current.date() not in holidays_set:
            added += 1
    return current

def compute_estimated_delivery_datetime(emission_iso: str, expected_days: int, holidays: Optional[Iterable[date]] = None) -> Optional[str]:
    if not emission_iso or expected_days is None:
        return None
    try:
        emission_dt = parse_iso_datetime(emission_iso)
    except Exception:
        return None
    result_dt = add_business_days(emission_dt, int(expected_days), holidays)
    return result_dt.isoformat()

def find_delivered_event_date(events: List[Dict[str, Any]]) -> Optional[str]:
    """
    Percorre os eventos do mais recente para o mais antigo e retorna o 'Date'
    do primeiro evento cuja Description contém 'entrega finalizada' (case-insensitive).
    """
    for ev in reversed(events or []):
        desc = (ev.get("Description") or "").lower()
        if "entrega finalizada" in desc:
            return ev.get("Date")  # já vem em ISO da API (ex.: 2025-09-17T15:50:00-03:00)
    return None

def get_other_property_value(other_props: list[dict], field_key: str):
    for p in other_props or []:
        if p.get("FieldKey") == field_key:
            return (
                p.get("ContactValueName") or 
                p.get("ObjectValueName") or
                p.get("EnumValueName") or
                p.get("StringValue") or
                p.get("DateTimeValue") or
                p.get("IntegerValue")
            )
    return None

