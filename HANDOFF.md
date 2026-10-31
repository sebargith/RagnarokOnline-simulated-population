# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 13:57 -03:00 por Codex
Referencia: codex/single-agent-plan, commit_ref e05d6fc; documentación en commit posterior.
## Objetivo actual
P3: objetivos acotados del 9B sobre ejecución OpenKore; continuación real demostrada.
## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous. WIP raíz, m3-worktree y m4-field preservado.
- P2 circuito vivo caza/venta/compra/regreso registrado en 9cd0354.
- P3 e05d6fc: --intent, esquema dependiente del estado, servicio acotado y validación bajo lock.
- 111 tests OK. Prueba real 9B: continued, goal8, kills6, una acción completada, una inferencia.
- Checkpoint activo 6/8 sin intención pendiente; P1 detenido.
- Último snapshot prt_fild08 161,277, HP57/57, Zeny13, base4/job3.
- Raw P3: runtime/p1/evidence/p3-live-1793465840 (incluye intentos iniciales y final).
- Acceso autorizado a Ollama y aprobación de publicación disponibles otra vez.
## Decisiones vigentes
- 9B Qwen3.5 Q6_K existente, cero retries; gameplay independiente de inferencia.
- Nuevo objetivo solo tras completar el actual; fingerprint estricto rechaza trabajo obsoleto.
- No repetir operaciones financieras inciertas; sin consola ni recursos artificiales.
- Runtime/puertos/GPU/DB compartidos; no ejecutar prepare_m4 sobre clientes existentes.
## Pendientes y límites
- Asignar meta nueva con modelo real tras completar la actual: todavía solo simulado.
- Objetivos variados y conversación integrada pendientes; SearXNG último estado offline.
- Piloto no demuestra supervivencia general ni calidad social; naturalidad y escala aplazadas.
## Próxima acción
Completar la meta 8 y verificar una nueva meta acotada del 9B, sin borrar historial;
después revisar P3 y avanzar al conocimiento web P4 según alcance autorizado.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/evidence/P3-goal-boundary.md; docs/USER_GUIDE.txt.
- agent/goal_planner.py; scripts/run_p2_cycle.py; tests/test_goal_planner.py.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
