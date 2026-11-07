"""Carga de configuracion.

Usamos JSON en vez de YAML a proposito: la Tachyon del sitio de la demo no
tiene salida a internet, asi que no podemos garantizar `apt install
python3-yaml`. json es libreria estandar de Python, cero dependencias.
"""
import json


def load_config(path="config.json"):
    """Lee config.json y lo devuelve como dict. Se llama una sola vez, al
    arrancar main.py; si hay que cambiar un umbral o un puerto, se edita el
    archivo y se reinicia el servicio (no hay recarga en caliente)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
