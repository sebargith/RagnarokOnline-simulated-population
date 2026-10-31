# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 10:39 -03:00 por Codex
Referencia: codex/single-agent-plan, commit_ref 8f76877; metadatos de relevo en commit posterior.
## Objetivo actual
Un personaje normal desde nivel 1, ejecutor nativo OpenKore, 9B para objetivos y conocimiento.
## Estado comprobado
- Checkout de continuación: D:/Ragnarok Agents/m4-continuous (existente).
- Raíz D:/Ragnarok Agents sigue en codex/web-search, c1f7956; no implementar allí.
- Demos M3/M4 funcionales en su alcance; no prueban autonomía ni progresión general.
- Chat 07 inactivo/interrumpido; m4-field en b560852, documentación con WIP.
- status.json guardado: run 69798d3240904ea5a436a4ae07770373, failed, ciclo 1, sin objetivo compartido.
- Servicios actuales por verificar; Visitor entró gráficamente antes. No reinicié procesos.
## Cambios desde el último relevo
- Plan P1–P4, roadmap, arquitectura, estado y guía actualizados; ninguna implementación nativa nueva.
- Reglas de relevo, CLAUDE.md y exclusión de registro privado .ai añadidos.
- Validación: git diff --check, UTF-8 y 53 enlaces locales en 11 archivos; sin tests/runtime nuevos.
## Decisiones vigentes
- Mantener rAthena pre-Renewal, versiones fijadas, Qwen3.5 9B Q6_K y SearXNG local.
- OpenKore será único ejecutor; no basta activar ai con el controlador viejo enviando pasos.
- Primero un bot normal; después dos para cooperación/comercio, luego tres; cinco opcional.
- Naturalidad, comparación de modelos y prueba larga aplazadas. Ningún fork externo instalado.
## Incompleto / problemas / validaciones pendientes
- P1–P4 pendientes; SearXNG último estado offline (backend Docker); solo existe web poring fijo.
- WIP raíz: config/m2-candidates.json, fixtures/m2-scenarios.json, fixtures/m2-grounding-probes-v2.json.
- WIP m3-worktree: agent/dialogue.py, scripts/run_m3.py, tests/test_m3_dialogue.py.
- WIP m4-field: README, BRIDGE, CURRENT_STATE, ROADMAP, USER_GUIDE, evidencia M4-field. Preservar.
- Raíz tiene AGENTS/.gitignore/CLAUDE/HANDOFF locales sin commit para entrada; no mezclarlos con WIP.
- Checkouts comparten runtime/DB/puertos/GPU. No resetear DB, borrar recuerdos ni repetir transferencias.
- Registro automático falló; no reintentar con otro chat: ERROR: La marca está en codex 01a18098-cc5b-7820-8dca-d72eec18cd2a, pero esa conversación no pertenece a D:\Ragnarok Agents (su carpeta es otra). No se guardó la ficha.
## Próxima acción
Claude: aplicar AI_PROTOCOL, comprobar Git/procesos y entrar al checkout codex/single-agent-plan.
Implementar SOLO P1a: perfil normal separado y navegación nativa con progreso/cancelación/resultado,
un dueño de ejecución y sin LLM en el trayecto. Pruebas reproducibles y una integración corta.
Tras dos fallos iguales revisar antes de repetir. Commits pequeños y push; actualizar estado y relevo.
## Archivos relevantes
- m4-continuous/docs/NATIVE_AGENT_PLAN.md; docs/CURRENT_STATE.md; docs/USER_GUIDE.txt.
- docs/research/BOT_EXECUTION_OPTIONS.md; bridge/openkore/m1_bridge.pl; scripts/prepare_m4.py.
Registro previsto: D:/Ragnarok Agents/.ai/chats/INDEX.md; ficha local: runtime/relevo-codex-ficha.txt.
