"""Evaluacion de alertas por umbral de humedad.

Mantiene el ultimo nivel de alerta por nodo para no generar una alerta nueva
en cada lectura: solo cuando el nivel realmente cambia (histeresis simple).
"""
import time


class AlertEngine:
    def __init__(self, umbral_bajo=20, umbral_critico=10, logger=None):
        self.umbral_bajo = umbral_bajo
        self.umbral_critico = umbral_critico
        self.logger = logger
        self.activas = {}  # node -> nivel actual ("bajo" | "critico" | None)
        self.historial_alertas = []  # para GET /alarmas

    def evaluar(self, data):
        node = data.get("node")
        pct = data.get("humedad_pct")
        if node is None or pct is None:
            return None

        nivel = None
        if pct <= self.umbral_critico:
            nivel = "critico"
        elif pct <= self.umbral_bajo:
            nivel = "bajo"

        anterior = self.activas.get(node)
        if nivel != anterior:
            self.activas[node] = nivel
            if nivel:
                mensaje = (
                    f"Humedad CRITICA en {node}: {pct}% (regar de inmediato)"
                    if nivel == "critico"
                    else f"Humedad baja en {node}: {pct}% (riego recomendado)"
                )
                alerta = {
                    "node": node,
                    "nivel": nivel,
                    "humedad_pct": pct,
                    "mensaje": mensaje,
                    "ts": time.time(),
                }
                if self.logger:
                    self.logger.warning(mensaje)
                self.historial_alertas.append(alerta)
                self.historial_alertas = self.historial_alertas[-200:]  # tope simple
                return alerta
            else:
                if self.logger:
                    self.logger.info(f"{node} volvio a humedad normal ({pct}%)")
        return None

    def estado_actual(self):
        return [
            {"node": n, "nivel": lvl}
            for n, lvl in self.activas.items()
            if lvl is not None
        ]
