"""API REST local.

Usa http.server (libreria estandar) en vez de Flask: no podemos garantizar
`pip install flask` sin internet en el sitio de la demo. Misma idea que el
Proyecto 1 (hilo daemon sirviendo HTTP), expone los mismos endpoints:

    GET /status
    GET /lectura                          -> ultima lectura por nodo
    GET /history?desde=&hasta=&node=      -> historico filtrable
    GET /alarmas                          -> alertas activas
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# Dashboard HTML/CSS/JS autocontenido: sin CDN externo (no hay internet en el sitio),
# consume los mismos endpoints JSON via fetch() y se autorrefresca cada 5s.
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>Humedad de Suelo - Dashboard</title>
<style>
  body { font-family: -apple-system, Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; padding:24px; }
  h1 { font-size:1.4rem; margin-bottom:4px; }
  .sub { color:#94a3b8; margin-bottom:20px; font-size:0.9rem; }
  table { width:100%; border-collapse: collapse; background:#1e293b; border-radius:8px; overflow:hidden; }
  th, td { padding:10px 14px; text-align:left; border-bottom:1px solid #334155; }
  th { background:#0f172a; color:#94a3b8; font-size:0.8rem; text-transform:uppercase; }
  .bar { display:inline-block; height:10px; border-radius:5px; background:#334155; width:120px; position:relative; overflow:hidden; vertical-align:middle; margin-right:8px; }
  .fill { height:100%; border-radius:5px; }
  .ok { background:#22c55e; } .bajo { background:#eab308; } .critico { background:#ef4444; }
  .pct { font-weight:600; }
  .alertas { margin-top:24px; }
  h2 { font-size:1rem; color:#94a3b8; }
  .alerta-item { background:#450a0a; border:1px solid #991b1b; color:#fecaca; padding:8px 12px; border-radius:6px; margin-bottom:6px; }
  .status { color:#64748b; font-size:0.8rem; margin-top:20px; }
  .endpoints { margin-bottom:20px; }
  .endpoints a { color:#38bdf8; text-decoration:none; font-family:monospace; font-size:0.85rem;
    background:#1e293b; border:1px solid #334155; padding:4px 10px; border-radius:6px; margin-right:8px; }
  .endpoints a:hover { background:#334155; }
</style></head>
<body>
  <h1>Monitoreo de Humedad de Suelo</h1>
  <div class="sub">Particle Tachyon &middot; se actualiza cada 5s</div>
  <div class="endpoints">
    <a href="/status" target="_blank">GET /status</a>
    <a href="/lectura" target="_blank">GET /lectura</a>
    <a href="/history" target="_blank">GET /history</a>
    <a href="/alarmas" target="_blank">GET /alarmas</a>
  </div>
  <table>
    <thead><tr><th>Nodo</th><th>Profundidad</th><th>Humedad</th><th>Raw ADC</th><th>Hace</th></tr></thead>
    <tbody id="filas"></tbody>
  </table>
  <div class="alertas">
    <h2>Alertas activas</h2>
    <div id="alertas"></div>
  </div>
  <div class="status" id="status"></div>
<script>
function nivel(pct) { if (pct <= 10) return "critico"; if (pct <= 20) return "bajo"; return "ok"; }
function hace(ts) {
  const s = Math.floor(Date.now()/1000 - ts);
  if (s < 60) return s + "s"; return Math.floor(s/60) + "min";
}
async function refrescar() {
  try {
    const [lecturas, alarmas, status] = await Promise.all([
      fetch('/lectura').then(r => r.json()),
      fetch('/alarmas').then(r => r.json()),
      fetch('/status').then(r => r.json())
    ]);
    lecturas.sort((a, b) => a.node.localeCompare(b.node));
    document.getElementById('filas').innerHTML = lecturas.map(l => {
      const n = nivel(l.humedad_pct);
      return `<tr><td>${l.node}</td><td>${l.profundidad || '-'}</td>
        <td><span class="bar"><span class="fill ${n}" style="width:${l.humedad_pct}%"></span></span>
        <span class="pct">${l.humedad_pct}%</span></td>
        <td>${l.raw}</td><td>${hace(l.ts)}</td></tr>`;
    }).join('');
    const ad = document.getElementById('alertas');
    ad.innerHTML = alarmas.length
      ? alarmas.map(a => `<div class="alerta-item">${a.node}: humedad ${a.nivel}</div>`).join('')
      : '<div style="color:#64748b;">Sin alertas activas</div>';
    document.getElementById('status').textContent =
      `${status.total_lecturas} lecturas totales - ${status.nodos.length} sensores - uptime ${Math.floor(status.uptime_s)}s`;
  } catch (e) {
    document.getElementById('status').textContent = 'Error cargando datos: ' + e;
  }
}
refrescar();
setInterval(refrescar, 5000);
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    storage = None
    alert_engine = None
    start_time = None
    logger = None

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path in ("/", "/dashboard"):
            self._send_html(_DASHBOARD_HTML)
        elif parsed.path == "/status":
            self._send_json({
                "status": "ok",
                "uptime_s": round(time.time() - _Handler.start_time, 1),
                "total_lecturas": _Handler.storage.contar(),
                "nodos": _Handler.storage.nodos_distintos(),
            })
        elif parsed.path == "/lectura":
            self._send_json(_Handler.storage.last_by_node())
        elif parsed.path == "/history":
            desde = qs.get("desde", [None])[0]
            hasta = qs.get("hasta", [None])[0]
            node = qs.get("node", [None])[0]
            self._send_json(_Handler.storage.history(desde=desde, hasta=hasta, node=node))
        elif parsed.path == "/alarmas":
            self._send_json(_Handler.alert_engine.estado_actual())
        else:
            self._send_json({"error": "not found", "ruta": parsed.path}, status=404)

    def log_message(self, fmt, *args):
        if _Handler.logger:
            _Handler.logger.info("API %s - %s" % (self.address_string(), fmt % args))


def start_api(host, port, storage, alert_engine, logger):
    _Handler.storage = storage
    _Handler.alert_engine = alert_engine
    _Handler.start_time = time.time()
    _Handler.logger = logger

    server = ThreadingHTTPServer((host, port), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True, name="api_flask_like")
    t.start()
    logger.info(f"API escuchando en http://{host}:{port}  (/status /lectura /history /alarmas)")
    return server
