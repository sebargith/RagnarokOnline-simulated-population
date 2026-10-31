# Estado actual

Actualizado: 2026-10-31 11:15 (America/Santiago) por Claude. P1a completada.

## Decisión vigente

El usuario aprobó el [plan de un jugador con ejecución nativa](NATIVE_AGENT_PLAN.md).
Primero un personaje normal desde nivel 1 con OpenKore reactivo; después ciclo
individual, objetivos del 9B y conocimiento web. Cooperación y comercio siguen
como objetivo posterior. Naturalidad, comparación de modelos, prueba larga y M5
no bloquean la primera entrega.

## Dónde continuar

- Checkout existente: `D:/Ragnarok Agents/m4-continuous`.
- Rama: `codex/single-agent-plan`, creada desde `2e8f850`.
- Raíz `D:/Ragnarok Agents`: entrada al proyecto y relevo, en `codex/web-search`
  (`c1f7956`), anterior y con WIP. No implementar allí ni limpiar sus cambios.
- [HANDOFF](../HANDOFF.md) contiene referencias y la primera tarea de Claude.
  Los checkouts comparten runtime, servicios, GPU y puertos.
- El registro automático de la ficha falló: este chat pertenece a otra carpeta
  según AI Relay. Error literal en HANDOFF; no se reintentó con otra conversación.
  La ficha local queda en `D:/Ragnarok Agents/runtime/relevo-codex-ficha.txt`.
- Chat 07 está inactivo; su último turno quedó interrumpido. En
  `m4-field`, HEAD `b560852`, permanecen cambios de documentación sin commit:
  README, BRIDGE, CURRENT_STATE, ROADMAP, USER_GUIDE y evidencia M4-field.
  No se ha aceptado su cooperación general ni incorporado toda esa rama.

## Procesos y P1a — 2026-10-31 11:15 -03:00

- Árbol de tests colgado de Codex (pwsh 67520 → 49236 → 44956, `unittest`
  inactivo con un listener simulado) cerrado por Claude con autorización del
  usuario. La suite actual termina en ~5 s (57 tests OK).
- OpenKore agent/peer/third de `m4-field` (PID 30496/60476/43560, `--ai=off`,
  8765–8767) siguen vivos y sin tocar. No ejecutar `prepare_m4.py` mientras
  existan: reasigna esos puertos.
- P1a implementada y probada en vivo: perfil separado `runtime/p1/openkore/solo`,
  personaje Tarin (novato nivel 1, `new_1-1`), OpenKore `--ai=manual`, puerto 8770,
  registro propio `runtime/p1/processes.json`. Cliente P1 detenido al terminar.
  [Evidencia y límites](evidence/P1a-native-navigation.md).
- rAthena, MariaDB y Ollama con listeners; 8080 (SearXNG) sin listener.

## Base comprobada y límites

- rAthena pre-Renewal, protocolo 20130807; versiones en
  [configuración fijada](../config/versions.json). OpenKore y el puente funcionan.
  Hoy los lanzadores de demo usan `--ai=off`; Python dirige acciones.
  Falta el adaptador nativo con un solo dueño de ejecución.
- M3: persistencia y conversación funcional en `ff635f5`; calidad social aplazada.
  [Evidencia](evidence/M3-persistence.md).
- M4: demo controlada y runtime continuo revisados, con identidades aisladas,
  kill/loot, cooperación de fixture, intercambio fijo y reconciliación sin replay.
  [Demo](evidence/M4-prototype.md), [continuación](evidence/M4-continuous.md).
  Esto no demuestra navegación general, habilidades, supervivencia ni progreso normal.
- Reparación de telemetría `f67fbfa`: 55 tests pasaron en su revisión anterior.
  Telemetría desconocida pausa admisiones; fallo persistente conserva `phase: failed`.
  No se han repetido tests de código en este turno documental.
- Estado guardado leído en `runtime/m4/live/status.json`: run
  `69798d3240904ea5a436a4ae07770373`, `running: false`, `phase: failed`,
  ciclo 1, error `Bounded patrol found no eligible shared visible target`.
  Es un archivo de una ejecución previa; no prueba qué servicios están vivos ahora.
- El coordinador observó a Visitor dentro de Prontera (152,180) tras login gráfico.
  Launcher: `D:/Ragnarok Agents/runtime/player-client/Play-Local.cmd`.
  Credenciales en el archivo local PLAYER_ACCOUNT.txt, nunca en Git.
  No se reinició cliente, servidor, DB ni controlador durante esta preparación.
- Qwen3.5 9B Q6_K seleccionado; mantener
  [presupuesto operativo](../config/m2-operating.json). No descargar otro modelo.
  Ollama reutiliza el almacén existente `D:/Local_AI/Models/Ollama`.
  RAM disponible mínima 2 GiB, GPU total máxima 14.336 MiB.
- SearXNG local en 127.0.0.1:8080: último estado conocido offline por backend
  Docker. El gameplay integra solo el disparador fijo `web poring`; la búsqueda
  general autónoma está pendiente. La [prueba anterior](evidence/Web-search-slice.md)
  no prueba disponibilidad actual.
- [Investigación de ejecutores](research/BOT_EXECUTION_OPTIONS.md): revisión de
  fuentes, sin instalar ni probar proyectos externos.

## Cambios preservados

- Raíz: config/m2-candidates.json, fixtures/m2-scenarios.json y
  fixtures/m2-grounding-probes-v2.json. Fuera de los commits de este relevo.
- m3-worktree: agent/dialogue.py, scripts/run_m3.py, tests/test_m3_dialogue.py,
  trabajo de pulido inconcluso. No atribuirle los tests del baseline.
- m4-field: experimentos y documentación de Chat 07, separados de esta base.
- No borrar bases, recuerdos, perfiles, transferencias pendientes ni instalaciones.

## Próxima acción única

Resto de P1 sobre el mismo perfil nativo: combate y recogida con las tareas de
OpenKore, y una respuesta local de recuperación (HP/SP), sin inferencia, con
evidencia y latencia medida. Mantener un solo ejecutor. No iniciar P2–P4.
