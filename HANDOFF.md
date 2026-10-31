# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 13:24 -03:00 por Codex
Referencia: codex/single-agent-plan, commit_ref 3463953; documentación en commit posterior.
## Objetivo actual
Un jugador normal con ejecución nativa; completar el piloto individual antes del 9B general.
## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous; raíz codex/web-search con WIP: no implementar allí.
- P1, P2a portales/diálogo, P2b tiendas y P2c Apple en descanso implementados.
- P2d ciclo persistente, consulta de resultados sin replay y checkpoint previo al envío.
- 94 tests OK (13 nuevos), syntax Perl/compileall/diff-check OK.
- Prueba viva: envío c_1 y cierre, consulta de su kill al reiniciar, continuación y cierre de objetivo.
- Objetivo 2/2 completo, 2 drops, cero muertes e inferencia; última reanudación envió cero acciones.
- Fin: Tarin prt_fild08 156,243, 57/57 HP, base4/job3, 10 Zeny.
- Cliente P1 detenido al terminar. Perfil solo/manual, puerto8770, cuenta2000030.
- Los tres clientes m4-field fueron verificados vivos y no tocados; tampoco servidor/DB/Ollama/Visitor.
## Cambios desde el último relevo
- Puente 1238a3d: query_result de solo lectura por sesión y flag de inventario truncado.
- Ciclo 3463953: agent/solo_cycle.py, scripts/run_p2_cycle.py, tests/test_p2_cycle.py.
- Revisión delegada sin escrituras: se corrigieron aislamiento de sesión y barreras de inventario/snapshot.
- Evidencia: runtime/p1/evidence/cycle-1793463752 (copias de events, state, status).
## Decisiones vigentes
- Un ejecutor nativo por personaje; travel caminable, no MapRoute/pagos.
- No repetir intención pendiente: consultar resultado; caché perdida o nueva sesión bloquean.
- Checkpoint runtime/p1/cycle/state.json; solo resultados confirmados cuentan progreso.
- Logs rotativos, history24; RAM libre2GiB/GPU14336MiB; sin LLM por tick.
- Mantener 9B Q6_K y SearXNG; naturalidad, escala y prueba larga aplazadas.
## Incompleto / límites
- Circuito integrado de tiendas probado con estados reproducibles, no vivo: este run no necesitó tienda.
- Objetivo guardado completo; --goal-kills solo inicializa, no sustituye ni reinicia ese objetivo.
- Falta interfaz para asignar otro objetivo conservando historial; no borrar checkpoint para continuar.
- Piloto fijo Tarin/prt_fild08/Fruit Gardener; selección de objetivos aún ignora peligro.
- Caché de resultados de un boot: perderla requiere conciliación/revisión, no reenvío.
- SearXNG último estado offline; P3/P4 pendientes. P2 aceptación completa aún abierta.
- WIP raíz, m3-worktree y m4-field preservado. Runtime/DB/puertos/GPU compartidos.
## Próxima acción
Nuevo objetivo explícito sin borrar historial y observar abastecimiento integrado cuando haya necesidad real.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/USER_GUIDE.txt; docs/evidence/P2d-persistent-cycle.md.
- agent/solo_cycle.py; scripts/run_p2_cycle.py; tests/test_p2_cycle.py; bridge/openkore/m1_bridge.pl.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
