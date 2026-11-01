# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Claude (P5 paso 3, campos de caza)
Referencia: rama codex/single-agent-plan; código en 586de19 + 6553c7e, docs en el último commit.
## Objetivo actual
P5: un novato nuevo de nivel 1 decide solo cómo progresar hasta primera clase; luego
comunidad. Dos funciones de modelo: planner inteligente (nube) y chat local.
## Estado comprobado
- Único relevo: este archivo. Checkout D:/Ragnarok Agents/m4-continuous; la raíz
  (codex/web-search, WIP M2) no se implementa. WIP preservado en m3-worktree y m4-field.
- P1–P3 hechos en su alcance: navegación, combate, loot, recuperación, portales,
  NPC/tienda, metas persistentes, propuestas del 9B validadas, exploración. 127 tests OK.
- P3: última meta 9/9, sin intención pendiente; cancelación viva y latencia sin medir.
- P4 parcial: consulta standalone (inference/mechanics.py) con SearXNG activo en 8080;
  dos muestras reales sin evidencia útil. No conectada al planner.
- P5 paso 1 hecho: inference/openai_compat.py + inference/roles.py + config/model-roles.json
  (planner/chat, respaldo local, claves por entorno o runtime/secrets/model-keys.env).
  Banco fixtures/p5-planner-bench.json; evaluación en docs/evidence/P5-model-eval.md:
  Groq gpt-oss mejor (96 %, ~0,8 s); Gemma 4 12B local 85 %; 9B 77 %; 9B think inviable; Gemini gratis con 503/429.
- Decisión aplicada (4fb70b1): planner groq-gpt-oss + respaldo gemma4-12b; chat gemma4-12b-chat
  local (ctx 8192, temp 0,7). 9B solo historial. Consumidores conectados a las funciones. 149 tests OK.
  Claves en runtime/secrets/model-keys.env (rellenadas por el usuario; no leer valores).
- P5 paso 2 hecho: stat_up/skill_up/equip/unequip en el puente (M1Progress.pm), con éxito solo por
  el paquete del servidor; agent/build_policy.py, config/p5-builds.json, config/p5-equipment.json,
  BuildPlanner en goal_planner.py. 166 tests OK. En vivo: Groq eligió novice-swordman; STR 5→11,
  NV_BASIC 0→2, Knife desequipado y reequipado, 10/10 confirmadas. Ver docs/evidence/P5-stats-equipment.md.
  Build de Tarin en runtime/p1/cycle/build.json.
- P5 paso 3 hecho: config/p5-monsters.json + config/p5-fields.json (scripts/build_p5_hunting.py, reproducible),
  agent/hunting.py (peligro, viables, opciones, temperamento + semilla), FieldPlanner, SoloCycle con field/outcomes
  y build en el ciclo; `run_p2_cycle.py run --p5`. 188 tests OK. En vivo: Groq eligió prt_fild06, travel 64 s,
  5 kills, venta y vuelta a prt_fild06; checkpoint complete 14/14, campo prt_fild06. Ver docs/evidence/P5-hunting-fields.md.
- Servicios (PIDs): MariaDB 50024, login 40760, char 55704, map 36528 (puertos 3306/6900/6121/5121), Ollama, Docker/SearXNG.
  Cliente P1 detenido; clientes m4-field no están corriendo.
- Visitor en grupo local Observer (20: @jumpto, @hide); carga tras el último reinicio [por verificar].
## Decisiones vigentes
- rAthena pre-Renewal, versiones fijadas; OpenKore manual es el único ejecutor.
- Solo portales caminables gratuitos; sin Kafra/pago. Sin premios, spawns ni progreso falso.
- El agente usa solo información legítima del cliente; el modelo propone, el ejecutor valida.
- Usuario: el 9B no basta; P5 usa planner Groq gpt-oss (respaldo Gemma 4 12B) y chat
  Gemma 4 12B local. Ver docs/evidence/P5-model-eval.md y plan P5.
- Un chat orquestador y una sesión por objetivo, en este checkout; un solo escritor.
## Incompleto / problemas / validaciones pendientes
- P4: selección de consulta demasiado amplia; status ok no implica evidencia suficiente.
- Peligro estimado (no fórmula exacta); en vivo sin retirada, muerte, subida de nivel ni reparto en el runner.
- Operación prolongada sin demostrar. ComfyUI del usuario puede ocupar la GPU (>14 GiB corta el runner).
- "M4 Poring" = etiqueta de la caché compartida tables/monsters.txt; no editarla.
- DB/puertos/GPU compartidos: no reiniciar servicios sin permiso; no ejecutar prepare_m4.py
  con clientes m4-field vivos; transacciones inciertas sin replay.
## Próxima acción
Revisión del orquestador del paso 3; luego P5 paso 4 (salir de la zona de entrenamiento por NPC). Pendiente aparte: revisión
humana del chat con Gemma.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/NATIVE_AGENT_PLAN.md; docs/USER_GUIDE.txt.
- docs/evidence/P2*.md, P3-*.md, P4-public-mechanics.md; agent/solo_cycle.py.
- bridge/openkore/m1_bridge.pl; bridge/lib/M1*.pm; inference/; config/m2-operating.json.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
