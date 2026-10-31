# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 14:02 -03:00 por Codex
Referencia: codex/single-agent-plan, commit_ref f4dbeac; documentación en commit posterior.
## Objetivo actual
Completar meta 8 y comprobar que 9B proponga una nueva meta sin borrar historial.
## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous; WIP raíz/m3-worktree/m4-field preservado.
- Meta real activa 6/8, sin acción pendiente. P1 detenido; otros procesos intactos.
- Prueba limitada: 14 acciones de patrulla, ninguna kill; terminó por action_budget.
- Dos snapshots prt_fild08 (165,240): lista local de monstruos vacía, HP57/57.
- Revisión delegada: la política repite seis coordenadas, sin ampliar búsqueda.
- No se sabe si hay monstruos en otra zona ni si existe fallo de percepción.
- 9B continuación real ya verificada; nueva meta del modelo solo simulada.
## Decisiones y límites
- No falsificar progreso, respawnear mobs ni borrar checkpoint para acelerar.
- Usar información legítima del cliente; no introducir estado global al agente.
- P1 detenido; DB/puertos/GPU compartidos; no reiniciar otros servicios.
- Mantener modelo 9B, límites de recursos y transacciones inciertas sin replay.
## Próxima acción
Mejorar exploración local más allá de la patrulla fija, con rutas válidas y
presupuestos finitos; probar una muestra breve antes de reanudar la meta.
## Archivos relevantes
- docs/evidence/P3-search-limitation.md; agent/solo_cycle.py; scripts/p1_hunt.py.
- bridge/openkore/m1_bridge.pl; docs/evidence/P3-goal-boundary.md.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
