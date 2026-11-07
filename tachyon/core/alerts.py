"""Evaluacion de alertas por umbral de humedad.

Mantiene el ultimo nivel de alerta por nodo para no generar una alerta nueva
en cada lectura: solo cuando el nivel realmente cambia (histeresis simple).
"""
import time


class AlertEngine:
    """Decide si una lectura de humedad merece alerta, y evita repetirla.

    Las alertas se evaluan en el nodo Python (la Tachyon), no en el
    firmware: el nodo solo mide y publica, toda la logica de "esto es
    preocupante" vive aqui, centralizada, para poder cambiar umbrales sin
    reflashear ninguna placa.
    """

    def __init__(self, umbral_bajo=20, umbral_critico=10, logger=None):
        """umbral_bajo/umbral_critico son % de humedad; por debajo de cada
        uno se considera ese nivel de alerta (critico manda sobre bajo)."""
        self.umbral_bajo = umbral_bajo
        self.umbral_critico = umbral_critico
        self.logger = logger
        self.activas = {}  # node -> nivel actual ("bajo" | "critico" | None)
        self.historial_alertas = []  # para GET /alarmas

    def evaluar(self, data):
        """Se llama con cada lectura que llega (una por sensor, cada ~10s).

        Devuelve una alerta nueva (dict) SOLO si el nivel de ese nodo acaba
        de cambiar respecto a la lectura anterior; si sigue igual de
        critico/bajo/normal que antes, devuelve None. Asi no se genera una
        alerta identica en cada ciclo mientras el sensor sigue seco.
        """
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
        """Alertas activas ahora mismo (para GET /alarmas): un nodo aparece
        aqui mientras su nivel sea "bajo" o "critico"; desaparece solo en
        cuanto vuelve a humedad normal."""
        return [
            {"node": n, "nivel": lvl}
            for n, lvl in self.activas.items()
            if lvl is not None
        ]
