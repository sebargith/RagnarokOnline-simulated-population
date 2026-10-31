# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 13:36 -03:00 por Codex
Referencia: codex/single-agent-plan, commit_ref c9077df; documentación en commit posterior.
## Objetivo actual
Jugador individual con OpenKore nativo; ciclo persistente y abastecimiento.
## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous; WIP previo raíz, m3-worktree y m4-field intacto.
- 31196aa: conciliación estricta de navigate/unknown/route_ended_off_target.
- Dos rutas anteriores conciliadas con sesiones nuevas y dos snapshots estables; sin replay ni falsa llegada.
- c9077df: hasta 5 s para movimiento tras terminar Task::Route si pos_to es destino exacto.
- 98 tests OK; 17 tests de ciclo tras reforzar snapshots; sintaxis Perl OK.
- Objetivo acumulado 4/4 completado; última continuación una acción de ataque, sin inferencia.
- Último snapshot prt_fild08 170,287, HP 41/57, Zeny 10. Cliente P1 detenido.
- La espera nueva no se probó con una ruta real después del cambio; tampoco hubo visita a tienda.
- Registro congelado: runtime/p1/evidence/cycle-reconcile-1793464544.
## Decisiones vigentes
- Conservar resultados unknown y conciliaciones; nunca repetir transacciones inciertas.
- Reconciliación solo para ruta terminada conocida; no aplica a ataque, loot, travel o tienda.
- Mantener rAthena, perfil OpenKore, 9B local, SearXNG y límites de recursos.
## Pendientes
- Verificar una ruta real con nueva espera y observar abastecimiento integrado cuando sea necesario.
- No inventar la causa de la primera ruta: su pos_to fue distinto del destino.
- Cliente/puertos/GPU/DB compartidos. No ejecutar prepare_m4 sobre clientes m4-field vivos.
## Próxima acción
Asignar otro objetivo explícito y continuar una prueba acotada con evidencia de navegación/tienda.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/USER_GUIDE.txt; docs/evidence/P2d-persistent-cycle.md.
- agent/solo_cycle.py; scripts/run_p2_cycle.py; bridge/lib/M1Navigation.pm; tests/test_p2_cycle.py.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
