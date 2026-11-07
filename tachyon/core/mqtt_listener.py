"""Hilo MQTT: escucha suelo/# y empuja cada lectura a una cola interna.

No usamos paho-mqtt (no se puede instalar sin internet en el sitio de la
demo). En su lugar reusamos el binario `mosquitto_sub`, que ya viene con
mosquitto-clients, y parseamos su salida en modo verbose (-v): cada linea es
"topico payload_json".
"""
import json
import subprocess
import threading


def start_listener(host, port, topic, out_queue, logger):
    """Arranca el hilo MQTT y vuelve de inmediato (no bloquea main.py).

    out_queue es una queue.Queue compartida con el hilo principal: este hilo
    solo mete lecturas ahi adentro, nunca toca SQLite ni alertas
    directamente (eso lo hace quien lea de la cola, en main.py).
    """
    def _run():
        # mosquitto_sub -v imprime "topico payload" por cada mensaje que
        # llega al topico suscrito; -t 'suelo/#' matchea cualquier nodo.
        cmd = ["mosquitto_sub", "-h", host, "-p", str(port), "-t", topic, "-v"]
        logger.info(f"Lanzando: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1)
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                mqtt_topic, payload = line.split(" ", 1)
                data = json.loads(payload)
                data["_topic"] = mqtt_topic
                out_queue.put(data)
            except ValueError:
                # linea sin payload JSON (ej. mensajes de estado de mosquitto_sub)
                logger.debug(f"Linea ignorada: {line}")
            except json.JSONDecodeError:
                logger.warning(f"Payload no es JSON valido: {line}")

    t = threading.Thread(target=_run, daemon=True, name="mqtt_listener")
    t.start()
    return t
