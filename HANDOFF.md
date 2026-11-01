# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Codex. Rama `codex/single-agent-plan`.

## Objetivo y límites
P5.4 observado de extremo a extremo en una muestra; no iniciar P5.5. Un escritor/runtime.
Mantener Groq planner y Gemma 4 12B respaldo/chat; no alterar personajes ajenos.

## Estado verificado
- Puente espera inventario listo y estable un segundo tras warp; timeout conserva
  warp y devuelve unknown si observación incompleta. 216 tests OK, Perl sintaxis OK.
- Conciliación específica de c_1: dos snapshots de sesión nueva, inventario completo,
  Zeny/EXP y posición coherentes; conserva resultado original y no repite diálogo.
  La lectura posterior no demuestra todos los estados intermedios.
- Una muestra: tutorial completo, Hanson trasladó a Izlude; Groq eligió Swordsman,
  build novice-swordman y campo prt_fild08. 11 acciones tutorial + 29 ciclo;
  kill y loot confirmados, meta 1/1. El nombre «M4 Poring» es alias de caché;
  evidencia previa sitúa fixture de recompensa en Prontera, no en este campo.
- Checkpoints tutorial y ciclo completos, inflight=null, historia conservada.
  Nilo detenido tras snapshot sin petición/tarea; prt_fild08 (336,211), HP38/46,
  base2/job1, Zeny0. MariaDB/rAthena y Ollama heredados activos; otros sin tocar.
- Evidencia: docs/evidence/P5-tutorial-exit.md. El chat principal revisará y pedirá
  aprobación para cualquier siguiente alcance. No iniciar el cambio de clase.

## Revisión del principal
- Checkpoints leídos: tutorial completo paso9 y ciclo1/1, ambos sin inflight.
- Eventos confirman c_37 cancelled, c_38 navigation_cancelled y c_39 killed.
- P5.4 aceptado para este recorrido; especie/origen del objetivo no acreditado
  solo por nombre. Siguiente propuesto: P5.5 (Job10 y primera clase), pendiente
  de aprobación del usuario. No se inició implementación ni otro runner.
