# Estado actual

## P3 — límite de búsqueda observado (2026-10-31 14:02)

- Una prueba de 14 acciones terminó sin encontrar monstruos visibles; meta
  real 6/8, sin intención pendiente y P1 detenido. La revisión delegada encontró
  que la patrulla repite seis posiciones sin ampliar cobertura. La lista vacía
  es solo percepción local, no prueba ausencia global ni fallo del servidor.
- Antes de verificar una nueva meta del 9B, mejorar exploración local y probar
  una muestra breve. [Evidencia](evidence/P3-search-limitation.md).

## P3 — continuación verificada con 9B real (2026-10-31 13:57)

- e05d6fc integra --intent, una admisión, propuestas restringidas por capacidades
  actuales y aplicación validada sobre el mismo objeto bajo el bloqueo del runner.
- Prueba real: modelo 9B seleccionado propuso continuar; resultado continued,
  goal8, kills6, una acción completada, sin intención pendiente. P1 detenido.
- 111 tests OK. Nuevas metas tras completar la actual: probadas con simulación,
  aún no en vivo. [Evidencia y comandos](evidence/P3-goal-boundary.md).
- Fallo anterior de permisos resuelto mediante aprobación autorizada.
  Documentación P2 pendiente confirmada en 9cd0354; publicación en curso.
- Snapshot final prt_fild08 161,277, HP57/57, Zeny13. No se alteraron servicios
  ni otros clientes. Mantener checkpoint 6/8, límites y modelo existentes.

## Registro anterior
Actualizado: 2026-10-31 13:24 (America/Santiago), Codex.

## Avance — circuito individual real (2026-10-31 13:41)

- Meta acumulada 8: Tarin 4→6 kills, cliente P1 detenido; objetivo activo
  6/8, sin intención pendiente. Continuó tras vender y comprar.
- Caza/loot → Prontera → venta cinco objetos (+18 Zeny) → compra Apple
  (−15 Zeny) → regreso a prt_fild08: resultados y deltas confirmados.
  [Evidencia y límites](evidence/P2e-live-supply.md).
- La ruta c_14 seguía activa al acabar el límite; una consulta de solo lectura
  recuperó completed/arrived sin reenvío antes de detener P1.
- 99 tests OK. `ac845da` corrige el script anterior para detenerse ante
  rechazos. Revisión de tienda delegada, sin otros procesos tocados.
- P2 demuestra el ciclo individual en este mapa y tienda; autonomía general,
  selección de peligro y operación prolongada siguen sin demostrarse.

## Dirección y checkout

- Un jugador normal primero; rAthena pre-Renewal y ejecución OpenKore nativa.
  9B local para objetivos/conversación y SearXNG para conocimiento, después.
  [Plan](NATIVE_AGENT_PLAN.md), [guía](USER_GUIDE.txt), [relevo](../HANDOFF.md).
- Continuar en `D:/Ragnarok Agents/m4-continuous`, rama `codex/single-agent-plan`.
  La raíz está en `codex/web-search` con WIP: es entrada al proyecto, no checkout
  de implementación. Se sincronizó su HANDOFF, que seguía atrasado en P1b.
- Claude dejó P1, P2a y P2b en commits hasta `500b542`, sin WIP en este checkout.
  Registro entrante AI Relay actualizado correctamente: 12 conversaciones,
  3 actualizadas. No se seleccionó ninguna conversación por fecha.

## Entregado y evidencia

- P1: navegar, atacar, recoger, respawn y recuperación local sin inferencia.
  [Navegación](evidence/P1a-native-navigation.md), [combate](evidence/P1b-native-combat.md).
- P2a: portales caminables gratuitos y diálogo NPC acotado, sin MapRoute.
  [Evidencia](evidence/P2a-portal-travel-npc.md).
- P2b: política de abastecimiento y venta/compra NPC con conciliación exacta.
  [Evidencia](evidence/P2b-npc-supply.md).
- P2c, primera entrega, commit `67c35eb`: usar Apple durante descanso, con
  paquete propio confirmado y disminución exacta de una unidad. Registro previo
  al envío en `runtime/p1/openkore/solo/healing-state.json`; timeout, reinicio
  incierto o fallo del registro bloquean uso adicional. No se repite el envío.
  [Evidencia y límites](evidence/P2c-local-healing.md).
- Verificación de este paso: 81 tests OK (4 nuevos), sintaxis Perl OK y
  compileall del runner/tests OK; git diff --check OK. El primer intento de
  tests aislado falló al cargar Perl (WinError 623); la suite elevada pasó.
- Una sola caza real, 91,3 s: 3 kills, 1 recogida, 0 muertes propias, Apple 1→0
  confirmada, 0 llamadas de inferencia. Final de la muestra: base 4/job 2,
  prt_fild08 (174,246), 22/57 HP, descansando. Ese HP es de fin de muestra,
  no del cierre del cliente, que permaneció descansando hasta detenerlo.
- Raw: `D:/Ragnarok Agents/runtime/p1/evidence/hunt-1793461320.json`, fuera de Git.

## Procesos y datos compartidos

- P2d persistente implementado, `1238a3d` y `3463953`: objetivo, fase,
  intención antes del envío y consulta de resultado sin replay. 94 tests OK;
  revisión delegada de solo lectura y correcciones de sesión/inventario.
  [Evidencia y comandos](evidence/P2d-persistent-cycle.md).
- Estado actual del piloto: objetivo 2/2 completo, sin intención pendiente.
  Tres procesos sucesivos: envío y cierre, consulta/continuación, cierre del
  objetivo con cero acciones nuevas. Dos kills, dos recogidas, cero muertes
  propias e inferencia. Snapshot final prt_fild08 156,243, 57/57 HP,
  base4/job3, 10 Zeny. Cliente P1 detenido al terminar.
- Estado persistente: `runtime/p1/cycle/state.json`; eventos/status acotados
  en esa carpeta. Copia congelada en `runtime/p1/evidence/cycle-1793463752`.
  Cambio de boot/sesión, caché perdida o resultado incierto bloquean; no borrar
  checkpoint para repetir una operación. El objetivo cumplido no se reinicia.
- El bloque P2c anterior conserva el estado de su prueba, no el estado actual.

- Tarin, cuenta 2000030, perfil P1 solo, manual, puente 8770: detenido tras esta
  prueba con prepare_p1.py stop. No se preparó/resetearon sus datos ni se añadió
  HP, objetos o experiencia. La Apple comprada por Claude se consumió.
- Antes de arrancar se verificaron los tres clientes m4-field vivos: PID
  30496/60476/43560, ai=off, puertos 8765–8767. No se tocaron. No ejecutar
  prepare_m4.py contra esos perfiles.
- rAthena/MariaDB/Ollama: heredados en ejecución; no reiniciados. SearXNG,
  último estado conocido offline. No se volvió a comprobar su backend.
- Visitor mantiene el grupo local Observer (20), puesto por Claude con permiso;
  conf/import/groups.yml fuera de Git. No se alteró esta configuración.
- Todos los checkouts comparten runtime, DB, GPU y puertos. Mantener recursos
  fijados: RAM libre ≥2 GiB, GPU ≤14336 MiB; modelo Qwen3.5 9B Q6_K existente.
- WIP preservado: raíz (config/m2-candidates.json, fixtures/m2-scenarios.json,
  fixtures/m2-grounding-probes-v2.json), m3-worktree (diálogo/run/tests) y
  m4-field (documentación Chat 07). No mezclar ni limpiar.
- Las demos M3/M4 conservan evidencia histórica en docs/evidence; no equivalen
  a progreso general. Naturalidad, prueba larga y escala a cinco aplazadas.

## Avance — conciliación y llegada diferida (2026-10-31 13:36)

- `31196aa`: conciliar únicamente navigate terminado con
  `unknown/route_ended_off_target`: sesión nueva y dos snapshots frescos,
  separados y estables, misma identidad/mapa, sin tarea ni movimiento.
  Conserva el resultado unknown, registra posición sin afirmar llegada y replantea.
  No aplica a compras, ventas, recogidas ni ataques inciertos.
- Primera ruta conciliada en prt_fild08 130,225; continuación logró kill 3,
  pero otra ruta devolvió el mismo unknown. Se revisó el diseño antes de repetir.
- En el segundo caso Task::Route terminó con destino establecido pero posición
  aún en movimiento. `c9077df` espera hasta 5 s en ese caso y solo confirma
  llegada si la posición llega; la primera ruta tenía destino distinto, por lo
  que la espera no se aplica. 98 tests OK; sintaxis Perl OK.
- Segunda ruta conciliada desde una sesión nueva en 170,280. Continuación:
  una acción de ataque, meta completa 4/4, sin replay ni inferencia; snapshot
  170,287, 41/57 HP, 10 Zeny. Cliente P1 detenido.
- La continuación no ejecutó una ruta tras la reparación, por tanto el tiempo
  de espera nuevo solo está verificado por tests, no por navegación real.
  Tampoco se activó abastecimiento; la prueba integrada de tienda sigue pendiente.
- Evidencia fuera de Git: `runtime/p1/evidence/cycle-reconcile-1793464544`.
  Revisión delegada independiente del puente; sin otros procesos tocados.

## Avance histórico — nuevo objetivo y ruta incierta

Commit `4d31c1e`: `set-goal --target-kills N` asigna una meta acumulada
solo tras completar la anterior, sin intención pendiente. Repetir la misma
meta es idempotente; conserva las últimas 24 operaciones y 24 objetivos.
96 tests OK; revisión delegada de condiciones de reinicio.

Prueba real: meta 2→4 guardada; tres rutas completadas, cuarta terminó
`unknown/route_ended_off_target`. Checkpoint `runtime/p1/cycle/state.json`
bloqueado, kills 2/4, intención c_4 conservada, última posición 131,226,
57/57 HP. No llegó a la tienda. Cliente P1 detenido; no borrar el checkpoint.

Próximo paso: inspeccionar la causa y diseñar conciliación segura de navegación
incierta desde observaciones frescas, sin repetir operaciones financieras.
Validar la recuperación antes de continuar el abastecimiento integrado.

## Pendientes y próxima acción

Integrar objetivos acotados del 9B (P3) sin bloquear la ejecución reactiva.
Meta de Tarin 6/8 guardada; no hay intención pendiente. P2 demuestra caza,
venta, compra y regreso en el piloto. Peligro general, SearXNG y comportamiento
prolongado siguen pendientes. No repetir operaciones financieras inciertas.
