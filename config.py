from datetime import date
import os

# =========================
#  Credenciais JAMEF
# =========================
JAMEF_USERNAME = os.getenv("JAMEF_USERNAME", "<email>")
JAMEF_PASSWORD = os.getenv("JAMEF_PASSWORD", "<senha>")

# URLs base da API JAMEF (produção por padrão)

JAMEF_AUTH_BASE_URL = os.getenv(
    "JAMEF_AUTH_BASE_URL",
    "https://api.jamef.com.br/auth/v1",
)

JAMEF_TRACKING_BASE_URL = os.getenv(
    "JAMEF_TRACKING_BASE_URL",
    "https://api.jamef.com.br/consulta/v1",
)
#=========================================================================
# URLs base da API JAMEF de QA

# JAMEF_AUTH_BASE_URL = os.getenv(
#     "JAMEF_AUTH_BASE_URL",
#     "https://api-qa.jamef.com.br/auth/v1",
# )

# JAMEF_TRACKING_BASE_URL = os.getenv(
#     "JAMEF_TRACKING_BASE_URL",
#     "https://api-qa.jamef.com.br/consulta/v1",
# )

# TTL do token em segundos (1h por padrão)
JAMEF_TOKEN_TTL_SECONDS = int(os.getenv("JAMEF_TOKEN_TTL_SECONDS", "3600"))  # 1h


# ------------------------ TESTE ------------------------
# Pipeline de TESTE: "[Cópia] - Gestão de Entregas"
PIPELINE_ID = 90001455

# IDs dos Stages a considerar (exclui "Entrega Concluída")
STAGE_IDS = [


]
# # ---------------------- PRODUÇÃO ---------------------
# PIPELINE_ID = 90000284
#
# STAGE_IDS = [
#     90001673,
#     90001674,
#     90001675,
#     90002319,
# ]
#
# STAGE_NAMES = [
#     "Faturado para Entrega",
#     "Em deslocamento",
#     "Atraso",
#     "Pendência",
# ]
# # ---------------------- PRODUÇÃO ---------------------


# Transportadora Origem (JAMEF)
TRANSPORTER_VALUE_JAMEF = "JAMEF TRANSPORTES"

# =========================
#  Ploomes
# =========================

# Chave Ploomes (pode deixar direto ou usar env var PLOOMES_KEY)
PLOOMES_KEY = os.getenv(
    "PLOOMES_KEY",
"****************************************************",
)

# FieldKeys dos campos do negócio
STATUS_DESCRIPTION_FIELD_KEY = "deal_..."
ESTIMATED_DELIVERY_DATE_FIELD_KEY = "deal_..."  # Previsão de Entrega (Data)
DELIVERY_DATE_UPDATED_FIELD_KEY = "ddeal_..."
NUMBER_INVOICE = "deal_..."
TRANSPORTER_FIELD_KEY = "deal_..."

# FieldKey do Nº da Nota Fiscal
ORDER_ID_FIELD_KEY = NUMBER_INVOICE

DELIVERY_STATUS_FIELD_KEY = os.getenv("DELIVERY_STATUS_FIELD_KEY")

# =========================
#  CNPJ matriz usado na Jamef
# =========================
TAX_ID_REGISTRATION = "<cnpj da empresa>"

# =========================
#  Feriados BR - 2025
# =========================
HOLIDAYS_BR = {
    date(2025, 1, 1),   # Confraternização Universal
    date(2025, 3, 3),   # Carnaval (segunda)
    date(2025, 3, 4),   # Carnaval (terça)
    date(2025, 4, 18),  # Sexta-feira Santa
    date(2025, 4, 21),  # Tiradentes
    date(2025, 5, 1),   # Dia do Trabalhador
    date(2025, 6, 19),  # Corpus Christi
    date(2025, 9, 7),   # Independência do Brasil
    date(2025, 10, 12), # Nossa Senhora Aparecida
    date(2025, 11, 2),  # Finados
    date(2025, 11, 15), # Proclamação da República
    date(2025, 12, 25), # Natal
}

# =========================
#  Execução / Observabilidade
# =========================

# DRY_RUN=False por padrão

DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() in ("1", "true", "yes", "y", "sim")

# Rate limit específico da Jamef: 1 requisição a cada 3 segundos
RATE_SLEEP_SECONDS_JAMEF = float(os.getenv("RATE_SLEEP_SECONDS_JAMEF", "3.0"))

# Log file JAMEF
LOG_FILE_JAMEF = os.path.join(os.path.dirname(__file__), "jamef-ploomes.log")

# Auditoria (CSV por execução)
AUDIT_DIR_JAMEF = os.path.join(os.path.dirname(__file__), "reports_jamef")
os.makedirs(AUDIT_DIR_JAMEF, exist_ok=True)