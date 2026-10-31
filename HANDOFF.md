# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 11:15 -03:00 por Claude
Referencia: codex/single-agent-plan, commit_ref 5bd2119; P1a en el commit siguiente.
## Objetivo actual
Un personaje normal desde nivel 1, ejecutor nativo OpenKore, 9B para objetivos y conocimiento.
## Estado comprobado
- Checkout de continuación: D:/Ragnarok Agents/m4-continuous. Raíz en codex/web-search (c1f7956): no implementar allí.
- P1a hecha: Tarin (cuenta 2000030, novato nv1 en new_1-1), perfil runtime/p1/openkore/solo,
  OpenKore --ai=manual, puente 8770, registro runtime/p1/processes.json. Cliente P1 detenido.
- En vivo: llegada confirmada, cancelación, timeout veraz, rechazos de un solo ejecutor. 57 tests OK.
- Clientes m4-field agent/peer/third (30496/60476/43560, 8765–8767) vivos, sin tocar.
- Árbol de tests colgado de Codex cerrado con autorización del usuario.
- rAthena/MariaDB/Ollama arriba; SearXNG 8080 sin listener.
## Cambios desde el último relevo
- bridge/lib/M1Navigation.pm (contrato puro), navigate/cancel en bridge/openkore/m1_bridge.pl.
- scripts/prepare_p1.py, scripts/p1_nav.py, tests/test_p1_navigation.py, evidencia P1a, README/estado/guía.
## Decisiones vigentes
- Mantener rAthena pre-Renewal, versiones fijadas, Qwen3.5 9B Q6_K y SearXNG local.
- Perfil nativo: Task::Route de OpenKore es el único dueño del movimiento; move paso a paso rechazado.
- P1a solo mismo mapa: el enrutador multi-mapa puede usar transporte NPC de pago; validar aparte.
- Primero un bot normal; después dos para cooperación/comercio, luego tres; cinco opcional.
## Incompleto / problemas / validaciones pendientes
- Desconexión durante ruta: implementada, [por verificar] en vivo (requiere cortar servidor compartido).
- blocked/unreachable solo con estados simulados. Snapshot.position es inicio de tramo, no posición actual.
- Resto de P1 (combate, loot, recuperación HP/SP), P2–P4 pendientes; SearXNG offline.
- WIP preservado: raíz (config/m2-candidates.json, fixtures m2), m3-worktree, m4-field (docs Chat 07).
- No ejecutar prepare_m4.py con los clientes m4-field vivos (reasigna 8765–8767).
- Checkouts comparten runtime/DB/puertos/GPU. No resetear DB, borrar recuerdos ni repetir transferencias.
## Próxima acción
Resto de P1 sobre el perfil nativo: combate y recogida con tareas OpenKore y recuperación local
HP/SP, sin inferencia, con evidencia y latencia medida. Presentar contrato antes de editar.
## Archivos relevantes
- docs/NATIVE_AGENT_PLAN.md; docs/CURRENT_STATE.md; docs/evidence/P1a-native-navigation.md.
- bridge/openkore/m1_bridge.pl; bridge/lib/M1Navigation.pm; scripts/prepare_p1.py; scripts/p1_nav.py.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
