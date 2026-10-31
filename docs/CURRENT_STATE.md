# Estado actual

Actualizado: 2026-10-31 (America/Santiago). Relevo a Claude.

## Decisión vigente

El usuario aprobó el [plan de un jugador con ejecución nativa](NATIVE_AGENT_PLAN.md).
Primero un personaje normal desde nivel 1 con OpenKore reactivo; después ciclo
individual, objetivos del 9B y conocimiento web. Cooperación y comercio siguen
como objetivo posterior. Naturalidad, comparación de modelos, prueba larga y M5
no bloquean la primera entrega. Este turno prepara documentos; no implementa
el adaptador ni modifica procesos del juego.

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

## Inventario de procesos — 2026-10-31 10:47 -03:00

Inspección de solo lectura con `Get-CimInstance Win32_Process` y
`Get-NetTCPConnection -State Listen`; la primera consulta CIM sin elevación
fue denegada, la consulta elevada funcionó. No se detuvo ningún proceso.

- OpenKore agent/peer/third: PID 30496/60476/43560, desde 08:38:44/47/49,
  plugins de `m4-field`, `--ai=off`, listeners 8765/8766/8767.
  Son clientes vivos; no demuestra que el controlador Python siga ejecutándose.
- Tests: PID 49236 y su hijo 44956, desde 2026-10-30 21:23:13,
  `-m unittest discover -s tests -v`. Es un árbol de una invocación, no evidencia
  de dos suites independientes. Persisten; bloqueo y causa no diagnosticados.
- MariaDB PID 29928:3306; rAthena login 29496:6900, char 51448:6121,
  map 24944:5121; Ollama PID 500:11434. Procesos y listeners presentes,
  sin prueba de salud funcional. No se observó listener en 8080.
- Docker fue reportado iniciado por Claude; su salud no se verificó en esta consulta.
- Antes de P1a, identificar el dueño de esos clientes/tests y resolver ocupación
  de puertos con cierre controlado cuando corresponda. No arrancar otro controlador
  contra los mismos clientes. Preservar servidor, DB y sesión gráfica.

Diagnóstico de Claude, 11:00 -03:00 (solo lectura):

- Tests: dueño = shell pwsh 67520 de Codex (Chat 07). Ejecutó en cadena
  `rg … m4_field`, `unittest discover`, `compileall`, `perl -c` y `git diff --check`.
  El hijo 44956 está inactivo (0,4 s de CPU, 1 hilo) con un listener local 55685
  propio de la prueba; cuelgue de un test con servidor simulado, sin efecto en el
  juego. Cerrar el árbol 67520→49236→44956 fue denegado al agente: requiere
  que el usuario lo detenga o lo autorice.
- Clientes OpenKore: solo ocupan 8765–8767 (puente) y sus sesiones de juego.
  P1a no los reutiliza ni los detiene: usará su propio perfil en
  `runtime/p1/openkore/`, otra cuenta/personaje y el puerto de puente 8770.
  No ejecutar `prepare_m4.py` mientras sigan vivos (reasigna 8765–8767).

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

Claude implementa la primera entrega P1: perfil normal separado y navegación
nativa con progreso, cancelación, llegada/fallo confirmados y un solo ejecutor.
Leer el [plan](NATIVE_AGENT_PLAN.md), comprobar procesos/puertos antes de probar
y usar pruebas reproducibles antes de una integración corta. No iniciar P2–P4
ni repetir cooperación de Chat 07 en esta entrega.
