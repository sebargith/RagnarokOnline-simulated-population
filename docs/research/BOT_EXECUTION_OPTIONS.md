# Ejecución de un bot autónomo: opciones investigadas

Revisión: 2026-10-31. Investigación de documentación y código público; no se
instalaron ni ejecutaron estos proyectos. La compatibilidad y calidad de sus
funciones no se consideran verificadas por sus README. Recomendación de diseño,
no una integración implementada ni aceptación del trabajo de campo de Chat 07.

El usuario aprobó esta dirección el 2026-10-31. El [plan vigente](../NATIVE_AGENT_PLAN.md)
detalla entregas y aceptación; la investigación siguiente conserva sus límites.

## Recomendación

Mantener rAthena y la instalación fijada de OpenKore. Probar primero un único
personaje normal desde nivel 1, usando capacidades nativas de gameplay en lugar
del movimiento y combate secuencial del controlador de demostración. Conservar
el 9B local para objetivos, interpretación, conversación y consultas públicas
acotadas cuando falte conocimiento. La ejecución reactiva debe continuar sin LLM.

## Proyectos y código revisado

| Proyecto | Mecanismo observado | Aprovechamiento propuesto | Límite relevante |
| --- | --- | --- | --- |
| [OpenKore](https://github.com/OpenKore/openkore) | IA de ataque y tareas de ruta/mapa, condiciones para habilidades/consumibles; eventMacro activa acciones por eventos | Primera opción para ejecución reactiva, navegación, combate y mantenimiento del personaje | Nuestro arranque actual usa `--ai=off`; integrar capacidades requiere cambiar la propiedad de ejecución y verificar resultados |
| [openkore-ai-v3](https://github.com/iskandarsulaili/openkore-ai-v3) | Código de orquestación heurística, acciones/validación, objetivos, y módulo de investigación web | Referencia de separación por capas, consultas ante problemas y control de llamadas | Experimental y muy extenso; no incorporar todo el fork ni su intercambio de experiencias entre bots |
| [openkore-mcp](https://github.com/diviatrix/openkore-mcp) | Plugin Perl no bloqueante que conecta herramientas con comandos de OpenKore | Referencia para exponer capacidades existentes al modelo | Su despachador permite comandos del registro completo; usar nuestra interfaz tipada restringida, no copiar esa autoridad general |
| [rust-ro-bot](https://github.com/pts1667/rust-ro-bot) | Planificación GOAP: acciones con precondiciones, efectos y costes, replanteamiento desde observaciones | Referencia para objetivos recombinables y recuperación tras fallos | Depende de la Bot API de rust-ro; no funciona directamente con nuestro rAthena. Revisar licencia antes de copiar código |
| [Population Engine en RagnarokOffline](https://github.com/Flux159/ragnarokoffline.app/tree/main/third-party/population-engine) | Personajes virtuales del lado del servidor, perfiles y estrategias de compañeros | Referencia de roles/reactividad; alternativa futura para población ambiental | Requiere cambios del servidor; incluye recursos virtuales y semánticas de shells que difieren del progreso normal de un jugador |

Se examinó también [Mimir](https://github.com/MegaWiz-Dev-Team/Mimir). Su
documentación actual se centra en conocimiento/RAG, NPC y servicios adicionales;
no es la base de ejecución de gameplay que necesitamos. El fork JokerSamaBR de
openkore-ai-v3 remite al original iskandarsulaili, usado como fuente principal.

Detalles que sustentan la comparación:

- OpenKore instalado: `src/AI/Attack.pm` selecciona habilidades según condiciones;
  `Task/Route.pm`, `Task/MapRoute.pm` y `AI/CoreLogic.pm` contienen ejecución de
  gameplay. [attackSkillSlot](https://openkore.com/wiki/attackSkillSlot),
  [useSelf_item](https://openkore.com/wiki/useSelf_item) y
  [eventMacro](https://openkore.com/wiki/EventMacro) documentan interfaces existentes.
- openkore-ai-v3: `AI_sidecar/ai_sidecar/orchestrator.py` (blob
  `f1d254729c28134358db419e7212d6bfd0cb0bfc`) llama a HeuristicService, valida
  acciones y produce comandos. Su fallback `attackAuto 2` ante error no es una
  política de supervivencia que debamos adoptar sin revisión.
- Su `web_research.py` (blob `df40b5264a1af0938f840075cf17d15dbbc7acac`)
  contiene una consulta JSON a SearXNG en loopback, timeout de 15 s y plantillas
  de preguntas. Guarda contenido de búsqueda como conocimiento; nuestra
  implementación deberá preservar fuente, incertidumbre y versión del juego.
  La integración completa de ese módulo no se ejecutó ni se verificó aquí.
- `goal_planner.py` del mismo proyecto contiene objetivos por defecto:
  el nombre de un módulo no implica planificación general sin reglas.
- openkore-mcp: `plugins/MCPBridge/MCPBridge.pl`, blob
  `fe35a11813fe1e574ca573bcde3352b5ee2d48fa`, integra `mainLoop_pre` y
  `tools/call`; termina en `Commands::run`. No interpreta ese retorno de texto
  como prueba suficiente de una acción completada en nuestro servidor.
- rust-ro-bot: `src/goap/planner.rs`, blob
  `4e72a423bc1a06ee3bfc9d6839aab7d14325ce3b`, usa búsqueda acotada por coste.
  `actions.rs`, blob `d944ff316dabcefa02f2858cdb4b70b72fbe43ef`, define
  precondiciones/efectos; sus efectos previstos no sustituyen observaciones.
  `agent.rs` reconstruye estado y planifica desde observaciones del bot.
- Population Engine: README del directorio vendorizado, blob
  `70aa52cbbada74f4a9aacd281afc39b5c97cc00f`, identifica como upstream
  [YlenXWalker/Population-Engine](https://github.com/YlenXWalker/Population-Engine).
  Describe munición virtual y gemas virtuales para ciertos compañeros. No
  trasladar esas facilidades al piloto de progresión normal.

Los blobs identifican contenido leído; los enlaces de rama pueden cambiar.
La licencia raíz de openkore-ai-v3 es GPL v2; la copia vendorizada de Population
Engine declara GPL v3. No se hizo una auditoría completa de licencias de todos
los componentes ni se copió código externo a nuestra implementación.

## Arquitectura propuesta para este proyecto

1. **Percepción:** estado fresco de personaje, actores, inventario, habilidades,
   diálogo NPC y resultados, con procedencia y separación por identidad.
2. **Ejecución reactiva:** OpenKore es el único dueño de movimiento/combate.
   Curación, peligro, habilidades y cancelación tienen prioridad local.
3. **Capacidades:** objetivos tipados como viajar, cazar, descansar, comprar,
   vender o hablar con NPC. Cada uno informa progreso, fallo y resultado
   observado. La lista crecerá sólo al verificar su implementación.
4. **Planificación:** seleccionar/revisar pasos a partir de necesidades y
   capacidades disponibles. Inicialmente basta un planificador pequeño;
   GOAP es una opción si la recombinación lo justifica, no un requisito.
5. **Conocimiento:** referencia pública versionada, recuerdos propios y web
   mediante SearXNG. Consultar ante una carencia real, con límites y caché;
   nunca exportar credenciales, conversaciones o recuerdos privados.

No activar IA nativa manteniendo simultáneamente nuestro controlador por
paquetes. El contrato de objetivos deberá adaptar límites, interrupción,
progreso y confirmación a tareas largas; el LLM no recibe consola libre ni
capacidad de escribir/ejecutar código descargado.

Una guía web puede sugerir dónde cambiar de clase. El bot deberá comprobar
mapa, requisitos y opciones que le presenta el servidor antes de actuar.
Si falta una herramienta, informará esa limitación; buscar en internet no crea
automáticamente una capacidad de ejecución. El bot deberá poder continuar con
rutinas seguras cuando búsqueda o inferencia estén indisponibles.

## Siguiente entrega propuesta

Demostrar primero un personaje separado, normal, nivel 1: navegación nativa,
combate adecuado a su estado, loot, descanso/consumibles y memoria persistente.
Después conectar un objetivo del 9B a esas capacidades y una consulta real de
conocimiento por SearXNG. El endpoint de búsqueda estaba offline en el último
handoff; restaurarlo/verificarlo es necesario antes de afirmar aprendizaje web.

Medir respuesta a peligro sin esperar al modelo. Probar decisiones y fallos con
observaciones guardadas; ejecutar verificaciones en vivo cortas y puntuales.
Las pruebas deben poder terminar y guardar un resumen sin un chat de Codex
consultando cada tick. No ampliar a cooperación hasta tener ese piloto útil.
