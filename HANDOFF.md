# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Codex. Rama `codex/single-agent-plan`.

## Objetivo y límites
P5.4: tutorial y salida normal de Nilo; no iniciar P5.5. Un solo escritor/runtime.
Mantener planner Groq gpt-oss-120b y respaldo/chat Gemma 4 12B, sin cambios.
No tocar personajes ajenos, fixtures, spawns, GM ni recolocaciones.

## Estado verificado
- Nilo creado cuenta 2000031, char 150007; partida inicial `new_2-1`, 48 puntos,
  Knife/Cotton. Repetir prepare conserva inventario; vacío/interrupción simulados.
- Build novice-acolyte añadida y elección de build ligada al destino; dos ofertas.
- Una muestra: portal a `new_2-2` confirmado, luego dos rechazos iguales
  `already_at_destination`; bloqueado en recepcionista, sin diálogos ni kill.
- Causa: snapshot usaba origen viejo de caminata; puente corregido para usar
  posición calculada. Regresión y 213 tests OK, sintaxis Perl OK; sin prueba viva.
- Cliente Nilo detenido tras confirmar sin petición/tarea; SQL guardado
  `new_2-2` (100,27), nivel 1, HP previo 40/40. Checkpoint bloqueado preservado
  `runtime/p5/cycle/tutorial.json`; eventos `runtime/p5/cycle/events.jsonl`.
- MariaDB PID22600, login40216, char12516, map31736 arrancados y activos;
  Ollama ya escuchaba. Procesos y puertos deben verificarse antes de tocarlos.
- [Evidencia](docs/evidence/P5-tutorial-exit.md); [estado](docs/CURRENT_STATE.md).

## Revisión principal y siguiente paso
- Informe de cierre solicitado y recogido del chat 12; estado bloqueado verificado
  leyendo tutorial.json: paso 1, inflight=null, c_1 completo y c_2/c_3 rechazados.
- Plan Chat 13 en docs/NEXT_CHAT_PLAN.txt: recuperación restringida y validación
  viva del snapshot/tutorial; PENDIENTE DE APROBACIÓN del usuario, no iniciado.
- Flujo nuevo: subchat informa al cerrar; principal revisa y planifica siguiente
  alcance con preguntas necesarias; usuario aprueba antes de ejecutarlo.
- No repetir muestras tras dos fallos iguales sin resolución fundamentada.
