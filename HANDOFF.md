# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 por Codex
Referencia: codex/single-agent-plan; ver historial Git para el commit final.
## Objetivo actual
Entregar para revisión la exploración viva y la nueva meta real del 9B, verificadas.
## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous; WIP raíz/m3-worktree/m4-field preservado.
- Una muestra de 90a65af: 30,641 s, 6 envíos, 6→8 kills, una ruta arrived,
  dos recogidas, un rechazo target_too_far; cero muertes e inferencia de caza.
- Monstruos visibles durante navigate (8/9 snapshots); no interrumpe por verlos,
  termina la ruta antes de atacar. Rayos rectos e historial de intentos conservados.
- Una propuesta real del 9B guardó hunt +1: checkpoint activo 8/9, sin acción
  pendiente, historial conservado. Cero acciones de juego en esa propuesta.
- P1 detenido; lectura final prt_fild08 (121,269), HP57/57, Zeny13.
- MariaDB50024/login40760/char55704/map36528 iniciados con datos existentes;
  quedan activos. Ollama preexistente, 9B cargado; M4 siguió detenido.
- Evidencia raw: runtime/p1/evidence/p3-live-1793468925/. Sin cambios de código.
## Decisiones y límites
- No falsificar progreso, respawnear mobs ni borrar checkpoint para acelerar.
- Usar información legítima del cliente; no introducir estado global al agente.
- DB/puertos/GPU compartidos; no reiniciar servicios ni clientes M4.
- Mantener modelo 9B, límites de recursos y transacciones inciertas sin replay.
- Dos kills contra objetivos llamados M4 Poring; no demuestra spawns naturales,
  cobertura general ni autonomía prolongada. No se crearon fixtures ni spawns.
## Próxima acción
El chat principal revisa evidencia y decide el próximo alcance. No arrancar
otra caza ni P4/múltiples jugadores como continuación automática de esta entrega.
En una futura reanudación conservar 8/9 y comprobar procesos/puertos primero.
## Archivos relevantes
- docs/evidence/P3-dynamic-exploration.md; agent/solo_cycle.py; bridge/lib/M1Explore.pm.
- bridge/openkore/m1_bridge.pl; docs/evidence/P3-goal-boundary.md.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
