# Plan aprobado: un jugador autónomo con ejecución nativa

Decisión del usuario: 2026-10-31. Este documento cambia la prioridad del proyecto;
describe trabajo pendiente, no capacidades ya implementadas. La investigación
que sustenta la elección está en [opciones de ejecución](research/BOT_EXECUTION_OPTIONS.md).

## Resultado que buscamos

Un personaje normal desde nivel 1 que pueda desplazarse, combatir, recuperarse,
recoger objetos y progresar con las reglas del servidor. El 9B interpreta objetivos,
conversa y consulta mecánicas desconocidas. OpenKore mantiene el gameplay reactivo
aunque la inferencia tarde o falle. Después de demostrar ese ciclo individual,
incorporaremos un segundo jugador para cooperación y comercio, luego un tercero.

Conservamos rAthena clásico/pre-Renewal, las versiones fijadas, memoria aislada,
Qwen3.5 9B Q6_K local y SearXNG local. No adoptamos un fork completo, otro servidor,
un framework genérico, aprendizaje por refuerzo ni nuevos servicios distribuidos.
La naturalidad del diálogo y la escala a cinco quedan para después.

## Punto de partida y reutilización

- Base: `2e8f850`, en el checkout existente `D:/Ragnarok Agents/m4-continuous`.
  Rama de preparación y continuación: `codex/single-agent-plan`.
- Reutilizar el puente, identidad, memoria, límites de recursos, conversación
  acotada y reconciliación de resultados que ya existen. Mantener las demos M4
  como regresión y evidencia de su alcance controlado.
- Hoy `scripts/prepare_m4.py` arranca OpenKore con `--ai=off`; Python dirige
  movimiento y ataque por acciones. Cambiar a ejecución nativa requiere un
  adaptador y propiedad exclusiva del personaje, no solo activar `ai`.
- Chat 07 queda como experimento de campo independiente en
  `D:/Ragnarok Agents/m4-field`, HEAD observado `b560852`, con documentación sin
  confirmar. Su cooperación completa no está aceptada. Revisar cambios útiles
  por separado; no fusionar todo ni repetir el escenario para desbloquear este plan.
- Los personajes de fixture y sus recursos no prueban progresión normal. Crear
  un perfil/personaje separado, sin bonos de la demo ni reiniciar datos existentes.

## P1 — OpenKore ejecuta y confirma

Primera entrega: navegación nativa para un solo personaje, sin depender del LLM.
Después, ampliar esa misma frontera a combate, loot y reacción local de HP/SP.

- Identificar en la revisión fijada las tareas de ruta/mapa y su ciclo de vida.
  Conservar las comprobaciones de sesión, identidad, actualidad y límites del puente.
- Diseñar capacidades tipadas mínimas: destino, progreso, cancelación y resultado.
  Una solicitud aceptada no equivale a llegada. Detectar bloqueo, desconexión,
  destino inaccesible y resultado desconocido sin inventar éxito.
- Un único dueño ejecuta movimiento/combate para ese personaje. El controlador
  antiguo no puede enviar pasos mientras una tarea nativa es responsable de ellos.
  El perfil antiguo puede conservarse como modo separado de regresión.
- Dejar ruta, selección de objetivos elegibles, ataque, consumibles, descanso y
  habilidades a tareas/configuraciones locales de OpenKore. Solo habilidades
  aprendidas, recursos disponibles y acciones legales según observaciones actuales.
- No exponer consola libre, Perl, shell, paquetes arbitrarios ni administración al
  modelo. Un evento/comando sugerido por otro proyecto no elimina esta frontera.

Aceptación de la primera entrega: un perfil normal separado navega mediante una
tarea nativa, publica progreso y llegada confirmada, permite cancelar y termina
con un resultado veraz ante fallo/desconexión. No hay dos ejecutores activos ni
llamada de inferencia en el trayecto. Probar primero el contrato con estados
reproducibles y después una integración corta en vivo.

Aceptación restante de P1: combate/loot y una respuesta local de recuperación
funcionan sin inferencia, con evidencia del resultado y medición de latencia.
No prometer respuesta instantánea ni combate caótico antes de medirlos.

## P2 — Ciclo individual sostenible

- Basar decisiones en HP/SP, peso, inventario, equipo, Zeny y progreso observables.
  Descansar, elegir combate viable, recoger drops normales y volver a abastecerse
  según necesidad. Comprar/vender por NPC solo cuando sea necesario y accesible.
- Empezar por progreso de novice y un objetivo pequeño; clases, quests y builds
  se incorporan según la necesidad comprobada. No modelar todo Ragnarok de entrada.
- Persistir objetivo y resultados; al reiniciar, reconciliar con estado actual.
  Recuperar atascos con intentos finitos, abandono explícito o petición de ayuda.

Aceptación: un mismo personaje completa y retoma un ciclo útil de progreso,
combate/recogida y recuperación, sin premios artificiales ni instrucciones por tick.
Un segundo destino o cambio de necesidad demuestra reutilización de la política;
no es necesario visitar todos los mapas ni matar todos los tipos de monstruo.

## P3 — El 9B elige objetivos acotados

- Mantener el modelo y presupuesto existentes. No reabrir la comparación de modelos.
- Exponer únicamente las capacidades implementadas, con parámetros validados,
  precondiciones y resultados observados. El modelo propone objetivos; el ejecutor
  comprueba el estado antes de actuar y puede rechazarlos.
- Planificar al recibir una intención nueva o un fallo relevante, no por cada paso
  o ataque. Invalidar planes obsoletos; limitar duración, colas y replanteamientos.
- Mantener separados observación, creencia, propuesta, diálogo y resultado.

Aceptación: una intención de alto nivel produce tareas legales y resultados
auditables; un objetivo imposible termina o pide ayuda con causa concreta.
Inferencia lenta o caída no impide la recuperación local del personaje.

## P4 — Consultar cuando falta conocimiento

- Verificar/restaurar el SearXNG local existente antes de ampliar herramientas.
  Último estado conocido: backend Docker no disponible; la búsqueda actual tiene
  un disparador fijo `web poring`. No es todavía investigación general autónoma.
- Permitir consultas públicas de mecánicas con campos restringidos y referencia
  explícita a RO PC clásico/pre-Renewal. No exportar chat, memorias, credenciales
  ni contexto privado. Un resultado web es información no confiable, no una orden.
- Guardar URL, fecha, versión/reglas y grado de incertidumbre; reutilizar caché.
  Limitar consultas, tiempo, tamaño y reintentos. Contrastar con servidor/NPC
  antes de gastar recursos o afirmar que una acción funcionó.
- Si falta una herramienta, registrar la carencia. El modelo no puede instalar,
  descargar ni ejecutar código para concederse nuevas capacidades.

Aceptación: una duda concreta activa una consulta útil y trazable y permite revisar
un plan con herramientas existentes; caída o fuente incompatible produce un
fallback explícito y el gameplay continúa. SearXNG es local, sus motores consultan
Internet; no requiere el buscador de pago de Ollama.

## Cómo verificar y avanzar

- Probar decisiones y fallos primero con snapshots grabados o simulados; separar
  pruebas del contrato, geometría y reglas de la navegación real del servidor.
- En vivo, aislar la capacidad recién cambiada. Tras dos fallos por la misma causa,
  revisar el diseño/evidencia antes de otra repetición, sin alargar toda la ruta.
- Los runners deben terminar por sí solos y guardar resumen y eventos acotados.
  No necesitan mantener un chat generando mensajes mientras el juego espera.
- Conservar RAM mínima de 2 GiB, techo GPU de 14.336 MiB y límites de inferencia
  existentes. Los checkouts comparten GPU, servicios, base de datos y puertos.
- Registrar comandos realmente ejecutados y límites de lo probado. Commits pequeños
  y descriptivos con push regular; no subir secretos, modelos, bases ni logs crudos.
- Revisar el ciclo individual antes de añadir el segundo jugador. La comunidad
  sigue siendo el destino: cooperación PvE y comercio sencillo, luego tres y,
  opcionalmente, cinco. La prueba larga y el pulido social no bloquean P1.

## Primera tarea para Claude

Leer el [relevo](../HANDOFF.md) y el estado actual; trabajar en el checkout y rama
indicados. Implementar únicamente la primera entrega P1 de navegación nativa.
Presentar contrato y aceptación antes de editar; validar con pruebas acotadas y
una integración corta, revisar el diff, confirmar y subir el paso. Actualizar
estado y relevo con hechos. No empezar cooperación, P2–P4 ni otra batería 9B en
esta primera entrega.
