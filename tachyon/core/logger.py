"""Logging rotativo (reutiliza el patron del Proyecto 1: RotatingFileHandler, max 10 MB)."""
import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name, log_path="logs/sistema.log", max_bytes=10 * 1024 * 1024, backup_count=5):
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # evita duplicar handlers si se llama mas de una vez

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s")

    fh = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger
