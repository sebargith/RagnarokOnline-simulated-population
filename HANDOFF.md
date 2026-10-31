# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 15:40 -03:00 por Claude
Referencia: rama codex/single-agent-plan, commit_ref b8af0a3; sin commit: ninguno.
## Objetivo actual
Un jugador normal (Tarin) con ejecución nativa OpenKore; ahora P4 (conocimiento web) y
decidir el modelo que reemplaza al Qwen3.5 9B para objetivos e informes.
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
- Usuario: el 9B no basta para decidir e informar; se evaluará un reemplazo (p. ej. Gemini
  gratis u otros). Hasta decidirlo no cambiar el modelo configurado.
- Un chat orquestador y una sesión por objetivo, en este checkout; un solo escritor.
## Incompleto / problemas / validaciones pendientes
- P4: selección de consulta demasiado amplia; status ok no implica evidencia suficiente.
- Selección de objetivo sin peligro; operación prolongada y spawns naturales sin demostrar.
- "M4 Poring" = etiqueta de la caché compartida tables/monsters.txt; no editarla.
- DB/puertos/GPU compartidos: no reiniciar servicios sin permiso; no ejecutar prepare_m4.py
  con clientes m4-field vivos; transacciones inciertas sin replay.
## Próxima acción
Decidir con el usuario el modelo de reemplazo y evaluarlo con prompts reales grabados
(metas, informe de estado, P4) antes de cambiar la configuración.
## Archivos relevantes
- docs/CURRENT_STATE.md; docs/NATIVE_AGENT_PLAN.md; docs/USER_GUIDE.txt.
- docs/evidence/P2*.md, P3-*.md, P4-public-mechanics.md; agent/solo_cycle.py.
- bridge/openkore/m1_bridge.pl; bridge/lib/M1*.pm; inference/; config/m2-operating.json.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
