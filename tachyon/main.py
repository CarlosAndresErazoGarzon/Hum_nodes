#!/usr/bin/env python3
"""Servicio de monitoreo de humedad de suelo - corre en la Particle Tachyon.

Arquitectura de hilos (misma idea que el Proyecto 1):
    - Hilo MQTT (mqtt_listener): escucha suelo/# via mosquitto_sub, empuja
      cada lectura a una cola interna.
    - Hilo de API (api/server.py): sirve /status /lectura /history /alarmas.
    - Hilo de reenvio (forwarder): best-effort hacia la plataforma web.
    - Hilo principal: toma de la cola, guarda en SQLite, evalua alertas y
      encola el reenvio (hace de "hilo de procesamiento").
"""
import os
import queue
import signal
import sys

from core.config_loader import load_config
from core.logger import get_logger
from core.mqtt_listener import start_listener
from core.storage import Storage
from core.alerts import AlertEngine
from core.forwarder import start_forwarder
from api.server import start_api

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    os.chdir(BASE_DIR)  # rutas relativas (data/, logs/) siempre respecto al proyecto
    cfg = load_config("config.json")

    logger = get_logger(
        "suelo",
        cfg["logging"]["log_path"],
        cfg["logging"]["max_bytes"],
        cfg["logging"]["backup_count"],
    )
    logger.info("=== Iniciando servicio de monitoreo de humedad de suelo ===")

    storage = Storage(cfg["almacenamiento"]["db_path"])
    alert_engine = AlertEngine(
        cfg["alertas"]["humedad_baja_pct"],
        cfg["alertas"]["umbral_critico_pct"],
        logger,
    )

    in_queue = queue.Queue()
    fwd_queue = queue.Queue()

    start_listener(cfg["broker"]["host"], cfg["broker"]["port"], cfg["broker"]["topic"],
                    in_queue, logger)
    start_forwarder(cfg["plataforma"]["url"], cfg["plataforma"]["token"], fwd_queue, logger,
                     cfg["plataforma"]["habilitado"])
    start_api(cfg["api"]["host"], cfg["api"]["port"], storage, alert_engine, logger)

    def handle_sigint(sig, frame):
        logger.info("Cierre solicitado (Ctrl+C / systemd stop), terminando limpiamente")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    logger.info("Servicio listo: hilos mqtt_listener, forwarder y api activos; "
                "procesamiento en hilo principal.")

    while True:
        try:
            data = in_queue.get(timeout=1)
        except queue.Empty:
            continue

        storage.insert(data)

        alerta = alert_engine.evaluar(data)
        if alerta:
            fwd_queue.put({"tipo": "alerta", **alerta})
        fwd_queue.put({"tipo": "lectura", **data})


if __name__ == "__main__":
    main()
