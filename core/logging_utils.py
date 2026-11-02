"""Logging estruturado com contexto, rotação e correlação."""
from __future__ import annotations
import logging
import logging.handlers
import json
import sys
import os
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Context variable para correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


class JSONFormatter(logging.Formatter):
    """Formatter JSON estruturado para logs machine-readable."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": correlation_id_var.get() or "-",
        }
        # Adiciona campos extras se existirem
        extra_fields = {k: v for k, v in record.__dict__.items()
                        if k not in ('name', 'msg', 'args', 'levelname', 'levelno',
                                     'pathname', 'filename', 'module', 'lineno',
                                     'funcName', 'created', 'msecs', 'relativeCreated',
                                     'thread', 'threadName', 'processName', 'process',
                                     'getMessage', 'exc_info', 'exc_text', 'stack_info')}
        if extra_fields:
            log_data["extra"] = extra_fields
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """Adiciona correlation_id automático aos records."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = correlation_id_var.get()
        if cid:
            record.correlation_id = cid
        else:
            record.correlation_id = "-"
        return True


def new_correlation_id() -> str:
    """Gera novo correlation ID."""
    return uuid.uuid4().hex[:12]


def set_correlation_id(cid: str):
    """Define correlation ID para contexto atual."""
    correlation_id_var.set(cid)


def clear_correlation_id():
    """Limpa correlation ID."""
    correlation_id_var.set("")


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[str] = None,
    json_format: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
) -> logging.Logger:
    """
    Configura logging estruturado.

    Args:
        level: DEBUG, INFO, WARNING, ERROR
        log_dir: Diretório para arquivos de log (None = só console)
        json_format: Se True, usa JSONFormatter; senão, formato humano
        max_bytes: Tamanho máximo por arquivo antes de rotacionar
        backup_count: Quantos arquivos de backup manter
        console: Se True, loga também no stdout
    """
    logger = logging.getLogger("anotadorpad")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    # Formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(correlation_id)-12s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Console handler
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        ch.addFilter(ContextFilter())
        logger.addHandler(ch)

    # File handler with rotation
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Log geral (rotativo)
        fh = logging.handlers.RotatingFileHandler(
            log_path / "anotadorpad.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        fh.setFormatter(formatter)
        fh.addFilter(ContextFilter())
        logger.addHandler(fh)

        # Log de erros separado (apenas ERROR+)
        eh = logging.handlers.RotatingFileHandler(
            log_path / "anotadorpad_errors.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        eh.setLevel(logging.ERROR)
        eh.setFormatter(formatter)
        eh.addFilter(ContextFilter())
        logger.addHandler(eh)

    logger.propagate = False
    return logger


def log_performance(logger: logging.Logger, operation: str, duration_ms: float, **context):
    """Log padronizado de performance."""
    logger.info(
        f"PERF {operation} | {duration_ms:.1f}ms",
        extra={"operation": operation, "duration_ms": duration_ms, **context}
    )


def log_detection(logger: logging.Logger, detector: str, pads_found: int, duration_ms: float, **context):
    """Log padronizado de detecção."""
    logger.info(
        f"DETECT {detector} | {pads_found} pads | {duration_ms:.1f}ms",
        extra={"detector": detector, "pads_found": pads_found, "duration_ms": duration_ms, **context}
    )


def log_user_action(logger: logging.Logger, action: str, **context):
    """Log padronizado de ação do usuário."""
    logger.info(
        f"USER {action}",
        extra={"action": action, **context}
    )


# Logger global padrão
_default_logger: Optional[logging.Logger] = None


def get_logger(name: str = "anotadorpad") -> logging.Logger:
    """Retorna logger global (inicializa se necessário)."""
    global _default_logger
    if _default_logger is None:
        _default_logger = setup_logging()
    return logging.getLogger(name)