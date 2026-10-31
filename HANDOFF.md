# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 por Codex
Referencia: codex/single-agent-plan; ver historial Git para el commit final.
## Objetivo actual
Completar meta 8 y comprobar que 9B proponga una nueva meta sin borrar historial.
## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous; WIP raíz/m3-worktree/m4-field preservado.
- Meta real activa 6/8, sin acción pendiente. P1 detenido; procesos heredados ausentes.
- Prueba limitada: 14 acciones de patrulla, ninguna kill; terminó por action_budget.
- Dos snapshots prt_fild08 (165,240): lista local de monstruos vacía, HP57/57.
- Revisión delegada: la política repite seis coordenadas, sin ampliar búsqueda.
- No se sabe si hay monstruos en otra zona ni si existe fallo de percepción.
- 9B continuación real ya verificada; nueva meta del modelo solo simulada.
## Decisiones y límites
- No falsificar progreso, respawnear mobs ni borrar checkpoint para acelerar.
- Usar información legítima del cliente; no introducir estado global al agente.
- DB/puertos/GPU compartidos; no reiniciar servicios ni clientes M4.
- Mantener modelo 9B, límites de recursos y transacciones inciertas sin replay.
## Próxima acción
La exploración dinámica está implementada y 115 tests pasan. El mapa local
produjo 41 candidatos desde (165,240); falta la prueba viva. Los PID registrados
de rAthena/MariaDB y M4 ya no existen y sus puertos no escuchan. No se iniciaron
servicios. Cuando estén disponibles, comprobarlos y hacer una sola muestra breve,
conservando la meta 6/8 y cualquier intención incierta sin replay.
## Archivos relevantes
- docs/evidence/P3-dynamic-exploration.md; agent/solo_cycle.py; bridge/lib/M1Explore.pm.
- bridge/openkore/m1_bridge.pl; docs/evidence/P3-goal-boundary.md.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
