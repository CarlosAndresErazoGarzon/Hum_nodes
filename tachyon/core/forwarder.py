"""Reenvio a la plataforma web (best-effort).

Usa urllib (libreria estandar) en vez de `requests` por la misma razon de
siempre: sin internet en el sitio no podemos instalar nada. En el sitio de
la demo, `habilitado=false` en config.json deja este hilo corriendo pero sin
intentar nada; se puede activar despues, cuando la Tachyon si tenga salida a
internet.
"""
import json
import threading
import urllib.error
import urllib.request


def start_forwarder(url, token, in_queue, logger, habilitado=True):
    """Arranca el hilo de reenvio hacia la plataforma web externa.

    in_queue la llena main.py con cada lectura y cada alerta ya procesada.
    Si habilitado=False (el caso de hoy, sin internet en el sitio), el hilo
    igual corre y sigue vaciando la cola, pero no intenta ninguna llamada de
    red: asi la cola nunca se llena sin limite mientras tanto.
    """
    def _run():
        while True:
            item = in_queue.get()  # bloquea hasta que main.py encole algo
            if not habilitado or not url:
                continue
            try:
                body = json.dumps(item).encode("utf-8")
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    logger.info(f"Reenviado a plataforma, status={resp.status}")
            except Exception as e:
                logger.warning(f"Reenvio fallido (sin internet en sitio es esperado): {e}")

    t = threading.Thread(target=_run, daemon=True, name="forwarder")
    t.start()
    return t
