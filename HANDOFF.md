# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 15:50 -03:00 por Claude
Referencia: rama codex/single-agent-plan, commit_ref 6efed78; plan P5 en el commit siguiente.
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
- Servicios: MariaDB 50024, login 40760, char 55704, map 36528, Ollama, Docker/SearXNG.
  Cliente P1 detenido; clientes m4-field no están corriendo.
- Visitor en grupo local Observer (20: @jumpto, @hide); carga tras el último reinicio [por verificar].
## Decisiones vigentes
- rAthena pre-Renewal, versiones fijadas; OpenKore manual es el único ejecutor.
- Solo portales caminables gratuitos; sin Kafra/pago. Sin premios, spawns ni progreso falso.
- El agente usa solo información legítima del cliente; el modelo propone, el ejecutor valida.
- Usuario: el 9B no basta; P5 usa planner (candidato Gemini gratis) y chat local; 9B de
  respaldo. Hasta evaluar no cambiar el modelo configurado. Ver plan P5.
- Un chat orquestador y una sesión por objetivo, en este checkout; un solo escritor.
## Incompleto / problemas / validaciones pendientes
- P4: selección de consulta demasiado amplia; status ok no implica evidencia suficiente.
- Selección de objetivo sin peligro; operación prolongada y spawns naturales sin demostrar.
- "M4 Poring" = etiqueta de la caché compartida tables/monsters.txt; no editarla.
- DB/puertos/GPU compartidos: no reiniciar servicios sin permiso; no ejecutar prepare_m4.py
  con clientes m4-field vivos; transacciones inciertas sin replay.
## Próxima acción
P5 paso 1 (sesión propia): adaptador OpenAI-compatible y config planner/chat; evaluar
candidatos con prompts reales grabados; el usuario elige. Luego pasos 2–7 del plan P5.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/NATIVE_AGENT_PLAN.md; docs/USER_GUIDE.txt.
- docs/evidence/P2*.md, P3-*.md, P4-public-mechanics.md; agent/solo_cycle.py.
- bridge/openkore/m1_bridge.pl; bridge/lib/M1*.pm; inference/; config/m2-operating.json.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
