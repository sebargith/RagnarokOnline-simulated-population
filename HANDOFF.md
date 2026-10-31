# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 13:31 -03:00 por Codex
Referencia: codex/single-agent-plan, commit_ref 4d31c1e; documentación en commit posterior.
## Objetivo actual
Jugador individual autónomo con OpenKore nativo; ciclo persistente y abastecimiento.
## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous. Raíz codex/web-search contiene WIP.
- Nuevo objetivo acumulado mediante set-goal; idempotente, history y goal_history acotados.
- 96 tests OK; revisión delegada de condiciones de reinicio.
- Meta 2→4 asignada; tres rutas completadas, cuarta unknown/route_ended_off_target.
- Checkpoint bloqueado kills 2/4, intención navigate c_4 conservada, sin compra/venta nueva.
- Última posición prt_fild08 131,226, HP 57/57. Cliente P1 detenido; no borrar checkpoint.
- Clientes m4-field y servicios existentes no tocados. Tienda integrada aún no probada en vivo.
## Decisiones vigentes
- No repetir una operación incierta; rAthena y observaciones confirman resultados.
- Un ejecutor nativo; sin LLM por tick; conservar modelo 9B y SearXNG local.
- Runtime, bases, puertos y GPU compartidos. WIP raíz, m3-worktree, m4-field preservado.
## Próxima acción
Investigar route_ended_off_target y conciliar navegación desde observaciones frescas sin
borrar intenciones ni repetir operaciones financieras; continuar abastecimiento cuando sea seguro.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/evidence/P2d-persistent-cycle.md; docs/USER_GUIDE.txt.
- agent/solo_cycle.py; scripts/run_p2_cycle.py; tests/test_p2_cycle.py; bridge/openkore/m1_bridge.pl.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
