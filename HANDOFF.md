# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 13:08 -03:00 por Codex
Referencia: codex/single-agent-plan, commit_ref 67c35eb; documentación en commit posterior.
## Objetivo actual
Un jugador normal autónomo con OpenKore nativo; 9B y conocimiento web después.
## Estado comprobado
- Checkout: D:/Ragnarok Agents/m4-continuous. Raíz codex/web-search con WIP: no implementar allí.
- Claude completó P1, P2a portales/diálogo y P2b tiendas hasta 500b542.
- P2c primera entrega: Apple en descanso seguro, consumo confirmado, registro previo al envío.
- 81 tests OK, Perl syntax OK, compileall OK; una caza 91,3 s, 3 kills, 1 loot, 0 muertes.
- Apple 1→0 confirmada por servidor. Cero inferencia. Raw hunt-1793461320.json.
- Fin de muestra: Tarin base4/job2, prt_fild08 174,246, 22/57 HP descansando.
- Cliente P1 detenido después; HP al detener no medido. Perfil solo/manual/8770, cuenta 2000030.
- Clientes m4-field 30496/60476/43560 verificados antes de iniciar P1; no tocados.
- No se reinició servidor/DB/Ollama ni se alteró Observer de Visitor.
## Cambios desde el último relevo
- M1Healing.pm, hook packet_useitem y recuperación; p1_hunt retiene evidencia de consumo.
- Estado, guía y arquitectura corregidos; HANDOFF de raíz estaba atrasado en P1b, sincronizado.
- AI Relay entrante OK: 12 conversaciones, 3 actualizadas.
## Decisiones vigentes
- Mantener rAthena pre-Renewal, versiones fijadas, Qwen3.5 9B Q6_K y SearXNG local.
- Un dueño de ejecución por personaje; solo travel por portales, nunca Task::MapRoute.
- Ledger healing-state.json: pending al reiniciar, timeout o fallo de escritura bloquean consumos.
- No borrar ese registro para reintentar; conciliar inventario y evidencia primero.
- Primero uno, luego dos para cooperación/comercio, tres y opcionalmente cinco.
## Incompleto / problemas / validaciones pendientes
- P2 persistente pendiente; consumible limitado a Apple y descanso sin amenaza ni tarea activa.
- Timeout/reinicio/rechazo de consumo: probados en módulo real con estados simulados.
- Retirada corregida P1b aún sin prueba viva específica; selección de monstruo ignora peligro.
- P3/P4 pendientes. SearXNG último estado offline, no comprobado de nuevo.
- WIP raíz, m3-worktree y m4-field preservado; no ejecutar prepare_m4.py sobre clientes vivos.
- Runtime, DB, puertos y GPU compartidos. No resetear datos ni repetir transferencias.
## Próxima acción
Implementar ciclo individual persistente caza/recuperación/abastecimiento con conciliación tras reinicio.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/USER_GUIDE.txt; docs/NATIVE_AGENT_PLAN.md.
- docs/evidence/P2c-local-healing.md; bridge/lib/M1Healing.pm; bridge/openkore/m1_bridge.pl.
- scripts/p1_hunt.py; scripts/p2_supply.py; tests/test_p2_healing.py.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
