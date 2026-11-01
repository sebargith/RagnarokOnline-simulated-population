# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Codex (control retomado)
Referencia: codex/single-agent-plan, base f258d9e; checkpoint en commit siguiente.

## Objetivo actual
P5.4: validar tutorial completo de Nilo y salida a campo con progreso normal.

## Estado comprobado
- Checkout D:/Ragnarok Agents/m4-continuous; único HANDOFF vigente. Git limpio al retomar.
- Claude dejó P5.1 roles de modelos, P5.2 stats/habilidades/equipo y P5.3 campos.
- Planner Groq gpt-oss-120b; respaldo/chat Gemma 4 12B local. Mantener configuración.
- P5.4 implementado en d64b41e, 207 tests según registro de Claude; aún sin prueba viva.
- Último estado registrado: juego parado, SearXNG/Ollama activos; verificar antes de arrancar.
- Nilo previsto: cuenta 2000031, puerto 8771, runtime/p5; aún no creado según relevo.

## Corrección verificada al recibir el relevo
- El supuesto defecto de stats del relevo anterior era incorrecto. PACKETVER 20130807
  usa char_clif.cpp >=20120307: seis stats a 1; char.cpp toma start_status_points=48.
- Los pares de stats y 0 puntos solo se aplican con PACKETVER <20120307.
- HP40/SP11 e items/start/savepoint coinciden con creación stock inspeccionada.
  Revisión independiente solo lectura confirma. No cambiar a stats 9/1.

## Decisiones vigentes
- rAthena pre-re, PACKETVER 20130807, ejecutor OpenKore manual único.
- Sin premios artificiales, spawns, recolocaciones ni comandos GM para bots.
- SQL de auditoría no informa decisiones del agente. Nunca leer/imprimir claves.
- Un chat de implementación; nuevos chats Terra 6.1 medio. Commits/push autorizados.
- Arrancar servicios existentes faltantes es rutina ya autorizada por el usuario.

## Pendiente y próxima acción
- Corregir prepare_p5: no reponer equipo si un personaje existente queda sin inventario.
- Resolver build novice-acolyte o coherencia de destinos ofrecidos por DestinationPlanner.
- Chat 12: verificar creación stock, cubrir reglas con pruebas y una muestra acotada del
  tutorial/salida/build/campo y al menos una kill normal. Conservar checkpoint ante fallos.
- P4 sin calidad útil/integración; cancelación exploratoria viva/latencia aún sin medir.
- No alterar etiquetas de vendor/OpenKore ni datos de Tarin/Visitor.

## Archivos relevantes
scripts/prepare_p5.py; agent/tutorial.py; config/p5-tutorial.json; config/p5-builds.json.
docs/CURRENT_STATE.md; docs/NATIVE_AGENT_PLAN.md; docs/evidence/P5-tutorial-exit.md.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
