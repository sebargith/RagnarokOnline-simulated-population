# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 11:45 -03:00 por Claude
Referencia: codex/single-agent-plan, commit_ref 5430a2a; P1b en el commit siguiente.
## Objetivo actual
Un personaje normal desde nivel 1, ejecutor nativo OpenKore, 9B para objetivos y conocimiento.
## Estado comprobado
- Checkout de continuación: D:/Ragnarok Agents/m4-continuous. Raíz en codex/web-search (c1f7956): no implementar allí.
- P1 completa. Tarin (cuenta 2000030): perfil runtime/p1/openkore/solo, OpenKore --ai=manual, puente 8770,
  registro runtime/p1/processes.json. Ahora en prt_fild08, nivel base 4 / job 2, guardado Prontera. Cliente detenido.
- P1a navegación; P1b attack/take/respawn y recuperación local (retirada, descanso). 61 tests OK.
- Run final: 6/6 muertes, 3 recogidas, 0 muertes, regeneración natural en descanso. Sin inferencia.
- Clientes m4-field agent/peer/third (30496/60476/43560, 8765–8767) vivos, sin tocar.
- rAthena/MariaDB/Ollama arriba (map-server PID 46040 tras reinicio ordenado); SearXNG 8080 sin listener.
- Visitor en grupo local Observer (Id 20: @jumpto, @hide) para mirar pruebas; conf/import/groups.yml fuera de Git.
## Cambios desde el último relevo
- bridge/lib/M1Combat.pm; attack/take/respawn/recovery en bridge/openkore/m1_bridge.pl; scripts/p1_hunt.py.
- tests/test_p1_combat.py; docs/evidence/P1b-native-combat.md; README/estado/guía.
## Decisiones vigentes
- Mantener rAthena pre-Renewal, versiones fijadas, Qwen3.5 9B Q6_K y SearXNG local.
- Perfil nativo: OpenKore manual es el único ejecutor; move paso a paso rechazado.
- Usuario aprobó colocar a Tarin en prt_fild08 desconectado (sin recursos), guardado Prontera 273,354.
- Solo mismo mapa: el enrutador multi-mapa puede usar transporte NPC de pago; validar aparte.
- Primero un bot normal; después dos para cooperación/comercio, luego tres; cinco opcional.
## Incompleto / problemas / validaciones pendientes
- Retirada con la política corregida (60/35 %, 15 celdas, 60 s): [por verificar] en vivo.
- Desconexión, robo de objetivo, item_lost: solo simulados. Elección de objetivo ignora su peligro.
- "M4 Poring" = etiqueta de la caché compartida tables/monsters.txt para 1002; no editarla.
- P2–P4 pendientes; SearXNG offline. No ejecutar prepare_m4.py con los clientes m4-field vivos.
- WIP preservado: raíz (config/m2-candidates.json, fixtures m2), m3-worktree, m4-field (docs Chat 07).
- Checkouts comparten runtime/DB/puertos/GPU. No resetear DB, borrar recuerdos ni repetir transferencias.
## Próxima acción
Revisar P1 con el usuario. P2 propuesto: viaje entre mapas solo por portales y diálogo NPC acotado.
## Archivos relevantes
- docs/NATIVE_AGENT_PLAN.md; docs/CURRENT_STATE.md; docs/evidence/P1a-native-navigation.md; P1b-native-combat.md.
- bridge/openkore/m1_bridge.pl; bridge/lib/M1Navigation.pm; bridge/lib/M1Combat.pm; scripts/prepare_p1.py; p1_nav.py; p1_hunt.py.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
