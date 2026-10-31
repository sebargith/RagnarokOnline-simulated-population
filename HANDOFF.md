# Relevo — Ragnarok Agents
Actualizado: 2026-10-31 12:45 -03:00 por Claude
Referencia: codex/single-agent-plan; P2a 069626e+f4363f3, P2b 4ccd7eb+838e2a0 (docs en el commit siguiente).
## Objetivo actual
Un personaje normal desde nivel 1, ejecutor nativo OpenKore, 9B para objetivos y conocimiento.
## Estado comprobado
- Checkout de continuación: D:/Ragnarok Agents/m4-continuous. Raíz en codex/web-search (c1f7956): no implementar allí.
- P1 completa. Tarin (cuenta 2000030): perfil runtime/p1/openkore/solo, OpenKore --ai=manual, puente 8770,
  registro runtime/p1/processes.json. Ahora en prt_fild08, nivel base 4 / job 2, guardado Prontera. Cliente detenido.
- P1a navegación; P1b attack/take/respawn y recuperación local (retirada, descanso). 61 tests OK.
- Run final P1b: 6/6 muertes, 3 recogidas, 0 muertes, regeneración natural en descanso. Sin inferencia.
- P2a hecha: travel solo por portales gratuitos sin NPC (bridge/lib/M1Travel.pm) y npc_talk acotado.
  Ida/vuelta prt_fild08↔Prontera + guía sur OK, Zeny Δ 0, sin mapRoute; 68 tests OK.
- P2b hecha: npc_sell/npc_buy (bridge/lib/M1Supply.pm) + política local scripts/p2_supply.py.
  Vendió botín (+25 z) y compró 1 Apple (−15 z) en Fruit Gardener; 77 tests OK.
  Tarin en prt_fild08 170,365 con 10 z y 1 Apple; cliente P1 detenido.
- Clientes m4-field agent/peer/third (30496/60476/43560, 8765–8767) vivos, sin tocar.
- rAthena/MariaDB/Ollama arriba (map-server PID 46040 tras reinicio ordenado); SearXNG 8080 sin listener.
- Visitor en grupo local Observer (Id 20: @jumpto, @hide) para mirar pruebas; conf/import/groups.yml fuera de Git.
## Cambios desde el último relevo
- P2a: bridge/lib/M1Travel.pm; travel/npc_talk en m1_bridge.pl (snapshot con npcs/ai_queue);
  scripts/p2_trip.py; tests/test_p2_travel.py; docs/evidence/P2a-portal-travel-npc.md; README/estado/guía.
- Durante npc_talk y tiendas se elimina la tarea autotalk de OpenKore (segundo ejecutor encontrado en vivo).
- P2b: M1Supply.pm; npc_sell/npc_buy en m1_bridge.pl (snapshot con weight y type/equipped);
  scripts/p2_supply.py; tests/test_p2_supply.py; docs/evidence/P2b-npc-supply.md.
## Decisiones vigentes
- Mantener rAthena pre-Renewal, versiones fijadas, Qwen3.5 9B Q6_K y SearXNG local.
- Perfil nativo: OpenKore manual es el único ejecutor; move paso a paso rechazado.
- Usuario aprobó colocar a Tarin en prt_fild08 desconectado (sin recursos), guardado Prontera 273,354.
- Entre mapas solo `travel` por portales caminables; Task::MapRoute sigue prohibido (Kafra/pago/objetos).
- Primero un bot normal; después dos para cooperación/comercio, luego tres; cinco opcional.
## Incompleto / problemas / validaciones pendientes
- Retirada con la política corregida (60/35 %, 15 celdas, 60 s): [por verificar] en vivo.
- Desconexión, robo de objetivo, item_lost: solo simulados. Elección de objetivo ignora su peligro.
- "M4 Poring" = etiqueta de la caché compartida tables/monsters.txt para 1002; no editarla.
- P2a probada; resto de P2, P3, P4 pendientes; SearXNG offline.
- P2a: portal_not_taken/unexpected_menu/shop/state_changed solo simulados; cambio de map-server = desconexión.
- P2b: fallos del servidor, state_mismatch y result_not_confirmed solo simulados; la Apple aún no se usa. No ejecutar prepare_m4.py con los clientes m4-field vivos.
- WIP preservado: raíz (config/m2-candidates.json, fixtures m2), m3-worktree, m4-field (docs Chat 07).
- Checkouts comparten runtime/DB/puertos/GPU. No resetear DB, borrar recuerdos ni repetir transferencias.
## Próxima acción
Revisar P2b con el usuario. Siguiente P2 propuesto: usar consumibles al recuperarse y ciclo persistente caza/recuperación/abastecimiento.
## Archivos relevantes
- docs/NATIVE_AGENT_PLAN.md; docs/CURRENT_STATE.md; docs/evidence/P1a-native-navigation.md; P1b-native-combat.md.
- bridge/openkore/m1_bridge.pl; bridge/lib/M1Navigation.pm; M1Combat.pm; M1Travel.pm; scripts/prepare_p1.py; p1_nav.py; p1_hunt.py; p2_trip.py.
- docs/evidence/P2a-portal-travel-npc.md; docs/evidence/P2b-npc-supply.md; M1Supply.pm; p2_supply.py.
Registro de chats: D:/Ragnarok Agents/.ai/chats/INDEX.md
