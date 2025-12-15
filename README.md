# 🚚 Integração Jamef → Ploomes (Gestão de Entregas)

Sincroniza automaticamente o **rastreamento de entregas da Jamef** com negócios no **Ploomes**, preenchendo:

- Descrição detalhada do status da entrega  
- Previsão de entrega (vinda da Jamef ou calculada)  
- Data de entrega realizada  
- Transportadora origem  
- Número da nota fiscal  
- Status da entrega em formato curto/limpo

> **Stack:**   3.13 · requests · API Jamef · API Ploomes

---

## 📁 Estrutura do Projeto

Exemplo de estrutura do repositório:

```text
.
├─ main_jamef.py           # Entry point (pipeline Jamef → Ploomes)
├─ config.py               # Configurações e credenciais (env + defaults)
├─ logging_config.py       # Setup de logging (arquivo + console)
├─ text_cleaner.py         # Funções de limpeza de status de rastreio
├─ jamef/
│   └─ client.py           # Cliente da API Jamef (login + rastreamento)
├─ ploomes/
│   └─ client.py           # Cliente da API Ploomes (deals + otherproperties)
├─ utils/
│   ├─ helpers.py          # Datas, prazos, regras de negócio
│   └─ http_retry.py       # Wrapper de requests com retry/backoff
└─ requirements.txt        # Dependências do projeto

🔧 Pré-requisitos
  3.13 instalado

Acesso à API da Jamef (usuário e senha)
Chave de API do Ploomes (User-Key)
Acesso à internet no servidor/PC que rodará o script

🐍 Configuração do Ambiente (venv com   3.13)
1. Clonar o repositório
bash
git clone https://github.com/SEU-USUARIO/SEU-REPO.git
cd SEU-REPO
Substitua SEU-USUARIO/SEU-REPO pelo caminho real do seu repositório.

2. Criar o ambiente virtual
Windows (PowerShell)
powershell

py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
Windows (CMD)
cmd

py -3.13 -m venv .venv
.\.venv\Scripts\activate.bat
Linux / WSL / macOS
bash

3.13 -m venv .venv
source .venv/bin/activate

3. Instalar dependências
Com o venv ativo:

bash
pip install -r requirements.txt
# ou, se não tiver requirements.txt:
# pip install requests
⚙️ Configuração (variáveis de ambiente)
Grande parte das configurações vem de config.py, mas podem (e devem) ser sobrescritas via variáveis de ambiente.

Jamef

bash

# Linux / macOS
export JAMEF_USERNAME="seu.usuario@empresa.com"
export JAMEF_PASSWORD="sua_senha_super_secreta"
export JAMEF_AUTH_BASE_URL="https://api.jamef.com.br/auth/v1"
export JAMEF_TRACKING_BASE_URL="https://api.jamef.com.br/consulta/v1"

# Windows PowerShell
$env:JAMEF_USERNAME = "seu.usuario@empresa.com"
$env:JAMEF_PASSWORD = "sua_senha_super_secreta"
$env:JAMEF_AUTH_BASE_URL = "https://api.jamef.com.br/auth/v1"
$env:JAMEF_TRACKING_BASE_URL = "https://api.jamef.com.br/consulta/v1"
A consulta de rastreamento usa TAX_ID_REGISTRATION (CNPJ do remetente) como documentoRemetente e o número da NF como numeroNotaFiscal.

Ploomes

bash
# Linux / macOS
export PLOOMES_KEY="SUA_USER_KEY_DO_PLOOMES"

# Windows PowerShell
$env:PLOOMES_KEY = "SUA_USER_KEY_DO_PLOOMES"
Os FieldKey dos campos do Ploomes (status, previsão, transportadora, NF etc.) são configurados em config.py:

STATUS_DESCRIPTION_FIELD_KEY
ESTIMATED_DELIVERY_DATE_FIELD_KEY
DELIVERY_DATE_UPDATED_FIELD_KEY
DELIVERY_STATUS_FIELD_KEY
ORDER_ID_FIELD_KEY
TRANSPORTER_FIELD_KEY
TRANSPORTER_VALUE_JAMEF

Pipeline e Estágios
Em config.py:

PIPELINE_ID = 90001455  # Exemplo
STAGE_IDS = [
    90010242,  # Faturado para Entrega
    90010243,  # Em deslocamento
    90010244,  # Atraso
    90010245,  # Pendência
]

🧪 DRY_RUN (modo teste)
O comportamento é controlado por DRY_RUN em config.py:

DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() in ("1", "true", "yes", "y", "sim")
Definição via ambiente:

bash

# Linux / macOS
export DRY_RUN="true"   # modo teste (não grava no Ploomes)
# ou
export DRY_RUN="false"  # modo produção (atualiza Ploomes)

# Windows PowerShell
$env:DRY_RUN = "true"
Quando DRY_RUN=true, o script apenas loga o que faria, sem alterar negócios no Ploomes.

🚀 Execução
Com o venv ativo e as variáveis configuradas:

bash
  main_jamef.py

O fluxo é:
Faz login na API da Jamef.
Busca negócios no Ploomes (pipeline + estágios configurados).
Para cada negócio:
Confere se a transportadora é JAMEF.
Lê a NF do negócio.
Consulta rastreamento na Jamef (documentoRemetente + numeroNotaFiscal).

Extrai:
Descrição rica: ex. INICIADO | ENTREGA REALIZADA | 11-12-2025
Previsão de entrega: da Jamef ou calculada (em ISO para DateTimeField)
Data de entrega real, se evento de entrega for identificado
Status limpo/curto, via limpar_status_rastreamento(...).
Atualiza campos no Ploomes (se não estiver em DRY_RUN).
Registra tudo em um CSV de auditoria.

Ao final, algo como:
text

Concluído. Negócios percorridos: 42 | CSV: .../audit_jamef_2025-12-12_11-19-03.csv

📊 Logs e Auditoria
Logs são gravados em LOG_FILE_JAMEF (definido em config.py) e também enviados para o console.

Cada execução gera um CSV em AUDIT_DIR_JAMEF, com colunas como:

deal id, stage id, title, transportadora

previsao calculada, entrega real

status execucao, Nota Fiscal, Status da Entrega