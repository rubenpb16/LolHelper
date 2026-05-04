"""
Logger centralizado para todos los módulos de LolHelper.
Escribe en consola y en fichero rotativo con formato estructurado.
"""
import logging
import logging.handlers
import sys

_LOG_FILE    = "lol_tracker.log"
_MAX_BYTES   = 5 * 1024 * 1024   # 5 MB por fichero
_BACKUP_COUNT = 3                  # máximo 3 ficheros antiguos

_FMT = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    """
    Devuelve un logger configurado con handlers de consola y fichero rotativo.
    Seguro para llamar múltiples veces con el mismo nombre (no duplica handlers).
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Consola — UTF-8 explícito para evitar problemas en Windows
    console = logging.StreamHandler(sys.stdout)
    console.stream.reconfigure(encoding="utf-8", errors="replace")
    console.setFormatter(_FMT)
    logger.addHandler(console)

    # Fichero rotativo
    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(_FMT)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
