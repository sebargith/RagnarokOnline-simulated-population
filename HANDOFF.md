# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 por Codex
Referencia: codex/single-agent-plan; ver historial Git para el commit final.
## Checkpoint — SearXNG activo
- Usuario inició Docker; SearXNG respondió en 8080. Dos consultas del 9B con
  fuentes no lograron sustentar una respuesta: categoría amplia y snippet ambiguo.
  Ver docs/evidence/P4-public-mechanics.md. Mejorar selección/evidencia antes de
  integrar al planner; P4 sigue incompleto.
## Checkpoint — P4 inicial (anterior al reintento)
- Interfaz standalone de mecánica pública, categorías cerradas y caché local;
  127 tests OK. No integrada al planner/runner, P4 incompleto.
- 9B disponible; búsqueda real terminó SearchUnavailable: backend Docker Linux
  no respondió tras intentar iniciar Docker Desktop. Ver docs/evidence/P4-public-mechanics.md.
- Siguiente: recuperar backend existente y validar una respuesta real con fuentes.
- Revisión 10 aceptada: 9/9 completo sin intención pendiente; cancelación viva
  y latencia no medidas; carrera de llegada conserva bloqueo conservador.
## Checkpoint — pruebas del runner
- Revisión independiente y del orquestador aceptó 60023ce. Cinco pruebas de
  integración con puente controlado; suite completa 123 OK. Sin cambios de runtime.
- Carrera de llegada bloquea conservadoramente; cancelación viva y latencia
  siguen sin demostrar. Último checkpoint vivo 9/9 completo; revisión principal aceptada.
## Checkpoint Chat 10
- Reacción de exploración implementada; 118 tests OK. Cancelación real y
  latencia sin demostrar: muestra única completó 9/9 con ataque inmediato.
- P1 detenido tras confirmar ausencia de tarea/petición; servicios existentes
  activos, M4 detenido. Sin nueva meta. Ver docs/evidence/P3-dynamic-exploration.md.
- La muestra quedó aceptada; no repetirla fuera del alcance vigente.
## Registro histórico Chat 09
La siguiente información describe el estado previo a Chat 10.
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
## Próxima acción histórica
Chat 10: reacción a objetivos elegibles durante exploración con cancelación
confirmada; no afectar viajes, transacciones ni recuperación de HP. Conservar
8/9 y comprobar procesos/puertos primero. Nuevos chats: Terra 6.1 medio.
El chat principal revisó run-result/planning-result y aceptó el alcance local;
no se ha demostrado autonomía general ni spawns naturales.
## Archivos relevantes
- docs/evidence/P3-dynamic-exploration.md; agent/solo_cycle.py; bridge/lib/M1Explore.pm.
- bridge/openkore/m1_bridge.pl; docs/evidence/P3-goal-boundary.md.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
