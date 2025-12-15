# logging_config.py
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(
    log_file: str = r"C:\Users\vinicius.guedes\Documents\api_jamef\jamef-ploomes.log",
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,   # 5 MB por arquivo
    backup_count: int = 7               # mantém 7 arquivos rotacionados
) -> logging.Logger:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    fmt = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")

    logger = logging.getLogger()  # root
    logger.setLevel(level)

    # evita handlers duplicados ao reconfigurar
    if logger.handlers:
        return logger

    # Arquivo com rotação
    fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    fh.setFormatter(fmt)
    fh.setLevel(level)
    logger.addHandler(fh)

    # Console (stdout) — útil para Docker/Lambda/execução manual
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(level)
    logger.addHandler(ch)

    return logger
