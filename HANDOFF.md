# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Claude (relevo a Codex)
Referencia: rama codex/single-agent-plan, commit_ref d64b41e; este relevo en el commit siguiente.
## Objetivo actual
P5: un novato nuevo de nivel 1 decide solo cómo progresar hasta primera clase; luego comunidad.
Planner Groq gpt-oss-120b (respaldo Gemma 4 12B local); chat Gemma 4 12B local.
## Estado comprobado
- Único relevo: este archivo. Checkout D:/Ragnarok Agents/m4-continuous; la raíz (codex/web-search,
  WIP M2) no se implementa. WIP preservado en m3-worktree y m4-field.
- P1–P3 en su alcance; P4 parcial (consulta standalone, sin evidencia útil, no conectada).
- P5.1 modelos (inference/roles.py, config/model-roles.json; claves en runtime/secrets/model-keys.env,
  rellenadas por el usuario, nunca leer ni imprimir valores). Evaluación: docs/evidence/P5-model-eval.md.
- P5.2 stats/habilidades/equipo con confirmación del servidor; P5.3 campos por nivel y peligro,
  build y campo dentro de run_p2_cycle --p5 (Tarin: prt_fild06, 14/14). Evidencias P5-*.md.
- P5.4 implementado (d64b41e, 207 tests OK) sin prueba en vivo: tutorial completo por NPC para Nilo
  (cuenta 2000031, puerto 8771), destino Izlude/Swordsman o Prontera/Acolyte elegido por el planner.
- Servicios del juego PARADOS (solo SearXNG 8080 y Ollama 11434). runtime/processes.json tiene PIDs
  muertos. Tarin y Nilo sin cliente. Visitor en grupo local Observer (20: @jumpto, @hide).
## Decisiones vigentes
- rAthena pre-Renewal, PACKETVER 20130807, versiones fijadas; OpenKore manual único ejecutor.
- Solo portales caminables gratuitos; sin Kafra/pago. Sin premios, spawns, recolocaciones ni @ para bots.
- El agente usa solo información legítima (cliente, tablas públicas generadas); el modelo propone y
  el código valida. Lecturas SQL solo como auditoría de evidencia, nunca como entrada del agente.
- Chat orquestador + una sesión por objetivo, en este checkout; un solo escritor.
## Incompleto / problemas / validaciones pendientes
- DEFECTO P5.4: prepare_p5.py crea stats a 1 + 48 puntos (regla PACKETVER ≥ 20151001). Este servidor
  (20130807) exige stats 1–9 con STR+INT=AGI+LUK=VIT+DEX=10 y 0 puntos (src/char/char.cpp char_make).
  Corregir antes de crear a Nilo; elegir el reparto inicial (p. ej. por la build) y documentarlo.
- Falta build novice-acolyte si se ofrece Prontera/Acolyte (o limitar a Izlude).
- Sin ver en vivo: subida de nivel y reparto en el runner, retiradas/muertes en P5, cambio de campo.
- P4 sin calidad suficiente; operación prolongada sin demostrar; ComfyUI puede ocupar la GPU.
- No editar vendor/openkore/tables/monsters.txt ("M4 Poring" es su etiqueta para 1002).
## Próxima acción
1) Corregir el defecto de stats (y la build de Acolyte) con pruebas. 2) Pedir permiso al usuario para
arrancar los servicios (revisar processes.json antes de m1.py start). 3) Prueba en vivo de P5.4:
crear Nilo, tutorial completo, destino, build, campo y ≥1 kill, con evidencia en
docs/evidence/P5-tutorial-exit.md. Después P5 paso 5 (cambio de clase en Job 10).
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/NATIVE_AGENT_PLAN.md (sección P5); docs/USER_GUIDE.txt.
- scripts/prepare_p5.py; config/p5-tutorial.json; agent/tutorial.py; agent/goal_planner.py; agent/solo_cycle.py.
- bridge/openkore/m1_bridge.pl; bridge/lib/M1*.pm; config/p5-*.json; scripts/run_p2_cycle.py.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
