# Revisión independiente del proyecto — 2026-11-02

Revisor: Claude (sesión de revisión, sin cambios de código ni operación).
Base revisada: rama `codex/single-agent-plan`, commit `0acf433`. Las referencias
`archivo:línea` corresponden a ese commit. OpenKore se revisó en la copia fijada
`vendor/openkore` (commit `e0b04ee70`, 2026-10-20). No se arrancaron ni tocaron
procesos, servicios, la base de datos ni a Nilo, y no se leyeron secretos.

Convención: **[verificado]** = lo comprobé en código local o en la fuente citada;
**[reportado]** = lo afirma una fuente de terceros y no lo comprobé;
**[opinión]** = juicio del revisor.

---

## 1. Resumen ejecutivo

**La dirección general es correcta, pero la implementación se apartó del plan
aprobado en un punto clave, y ese desvío explica la mayor parte del trabajo
reciente.**

- Lo correcto:
  - rAthena fijado como verdad del juego, con OpenKore sin interfaz gráfica como cliente;
  - controladores deterministas para lo frecuente y el LLM solo para metas acotadas, validadas contra el estado;
  - separar observación, creencia y resultado;
  - la privacidad del chat.

  Coincide con lo que mejor funciona en la literatura y en proyectos parecidos: Lyfe Agents, PIANO de Project Sid y AzerothCore Playerbots con `mod-ollama-chat`.
- El desvío: el plan decía *"Dejar ruta, selección de objetivos elegibles, ataque, consumibles, descanso y habilidades a tareas/configuraciones locales de OpenKore"* (`docs/NATIVE_AGENT_PLAN.md:55`). En la práctica, OpenKore corre en `--ai=manual` y solo se usan sus tareas de bajo nivel (`Task::Route`, `attack`, `take`). Python y Perl reconstruyeron lo que la IA nativa de OpenKore ya trae:
  - elegir el objetivo más cercano (`agent/solo_cycle.py:543-555`);
  - explorar el campo (`:556-588`, equivale a `lockMap` con `route_randomWalk`);
  - ir a vender y comprar (`scripts/p2_supply.py`, equivale a `sellAuto`/`buyAuto`);
  - retirarse y sentarse (`m1_bridge.pl:361-412`, equivale a `sitAuto`/`runFromTarget`);
  - viajar entre mapas con zonas a pie (`M1Travel.pm` y `agent/walk.py`, unas 1.460 líneas en `e574b18`), cuando ya existen `Task::CalcMapRoute`, `portalsLOS.txt`, `route_maxWarpFee` y `routeWeights`;
  - el peligro por monstruo (`agent/hunting.py`, en parte lo que hace `mon_control.txt`).
- El coste: cada ataque, recogida o paso de exploración es una intención con checkpoint, plazo y conciliación. Esa granularidad genera los casos límite que ocupan el ritmo actual:
  - resultados `unknown` o tardíos;
  - rutas que terminan "cerca";
  - viajes fallidos que hay que retirar;
  - bolsas sin salida.

  Desde el 2026-11-01 hay 43 commits: unos 16 son arreglos o conciliaciones, 6 son funciones nuevas y unos 21 son documentación. La comunidad, que es el objetivo, no avanza desde M4 (2026-10-30).
- Resultado práctico: Nilo lleva 175 kills y Base 9 tras muchas sesiones. La evidencia no muestra más de unos 15 minutos seguidos sin intervención (las tandas de 870 s acaban por presupuesto y se relanzan a mano) (`HANDOFF.md:54`: "NO acredita operación larga sin intervención"). Además, pasa gran parte del tiempo viajando a vender: va a la tienda con solo 5 objetos de botín (`scripts/p2_supply.py:21`), y la caza entre viajes dura unos 90 s de mediana (`agent/hunting.py:29`).

**Recomendación central [opinión]:** invertir la relación. Que Python y el LLM
decidan **qué** hacer (campo, build, umbrales de abastecimiento, cuándo cambiar de
clase, con quién agruparse) y lo traduzcan a **configuración de OpenKore**:
`lockMap`, `mon_control`, `routeWeights`, `sitAuto`, `buyAuto`/`sellAuto`,
`statsAddAuto`/`skillsAddAuto` y `route_maxWarpFee 0`. OpenKore en modo `auto`
ejecuta el **cómo**. La conciliación estricta queda solo para acciones
irreversibles: comercio, compraventa, cambio de clase, puntos y scripts NPC.
Se mide con una prueba acotada (1–2 días) antes de decidir. Después, adelantar la
capa social: 2 personajes con chat y grupo en el mismo campo, en lugar de pulir
más el grind en solitario.

**Actualización 2026-11-03 (ver [anexo](#7-anexo-proyectos-adicionales-evaluados)):**
la revisión de rdoc, ragnarokoffline.app y otros proyectos no cambia el orden de
R1–R5. Añade tres ajustes:
- R4/P4: la consulta de mecánicas debe ir primero a fuentes pre-Renewal
  concretas y cacheadas, sobre todo iRO Wiki Classic y los datos del propio
  rAthena, antes que a una búsqueda web general.
- Population Engine pasa de "futuro" a candidato concreto para la población de
  ambiente, después de R3 y con dos condiciones: verificar que funciona con
  PACKETVER 20130807 y que nunca sustituya a los 3–5 agentes núcleo.
- Un cliente web (roBrowserLegacy) es la vía más probable para que el usuario
  juegue junto a los agentes y haga la revisión ciega de R3. Falta verificar que
  sea compatible.

---

## 2. Evaluación por punto

### 2.1 Objetivo: ¿bien definido y medible?

- **Bien definido en lo individual.** La aceptación de P5 es observable: desde nivel 1, sin ayuda, premios ni recolocaciones, el personaje llega a Job 10 y cambia de clase, y cada decisión queda registrada con sus hechos (`docs/NATIVE_AGENT_PLAN.md:178-180`). Es un buen criterio [verificado].
- **Poco medible en lo que importa.** "Comunidad de jugadores IA creíbles" no tiene métricas. `ROADMAP.md` (M4) pide "human review of continuity, believable interaction and social quality" sin protocolo ni umbral, y esa revisión se ha aplazado dos veces: el 2026-10-30 y el 2026-10-31 (`ROADMAP.md:19-21,32-38,101`) [verificado].
- **Falta una métrica de autonomía.** La operación larga es el paso 6, al final, pero la autonomía es la condición para todo lo demás. Hoy no existe un "tiempo medio entre intervenciones" (MTBI) ni un objetivo para él.
- **Riesgo de objetivo [opinión].** Se optimiza el grind en solitario, la parte menos diferenciadora, porque OpenKore la resolvió hace dos décadas. La parte diferenciadora sigue en el nivel de las demos con fixture de M3/M4: memoria, relaciones, conversación, grupos y comercio entre agentes.

**Propuesta de métricas (sustituye a "creíble" sin más):**

| Dimensión | Métrica | Umbral inicial sugerido |
| --- | --- | --- |
| Autonomía | MTBI: horas entre intervenciones manuales; muertes con recuperación automática | ≥ 4 h por agente; 100 % de muertes recuperadas |
| Progreso | EXP/hora frente a una referencia humana grabada en el mismo campo | ≥ 50 % de la referencia |
| Continuidad | Hechos propios recordados tras reinicio; contradicciones por hora | 0 contradicciones con el registro |
| Social | Interacciones no guionizadas por hora (conversación de ≥3 turnos, grupo formado, intercambio) | ≥ 2/h con 3 agentes |
| Credibilidad | Revisión ciega: un observador lee 20 min de chat y registro de 4 personajes (1 humano) y señala los bots | Mejor que el azar no aceptado como "creíble"; registrar la tasa |

### 2.2 Arquitectura

**Lo que está bien [opinión, con evidencia]:**

- El puente por socket con token, épocas, una acción en vuelo y la diferencia entre `accepted`, `completed` y `unknown` (`docs/BRIDGE.md`, `bridge/openkore/m1_bridge.pl:173-190`) es correcto para acciones **irreversibles**. La conciliación del comercio M4 es buen trabajo.
- Las tablas públicas generadas desde los datos fijados (`config/p5-monsters.json`, `config/p5-fields.json`), los temperamentos por personaje y el registro de decisiones con `facts` sirven en cualquier arquitectura.
- El LLM nunca toca la consola ni los paquetes. Es más seguro que `openkore-mcp`, que termina en `Commands::run` (ver `BOT_EXECUTION_OPTIONS.md`), y que el agente de ragnarokoffline.app, que da a las cuentas del agente `@warp`/`@go`/`@load` (PR #193).

**El problema: se reconstruye lo que OpenKore ya trae** [verificado en `vendor/openkore`]:

| Necesidad del proyecto | Implementación propia | Equivalente nativo de OpenKore |
| --- | --- | --- |
| Viajar entre mapas solo por portales gratuitos y a pie | `M1Travel.pm` (383 líneas), `agent/walk.py`, `config/walk-zones.json`, `scripts/build_walk_zones.py`; `noMapRoute => 1` (`m1_bridge.pl:419-420,444`) | `Task::CalcMapRoute` con `budget` (`src/Task/CalcMapRoute.pm:72,96-105,609-610`) y `route_maxWarpFee` (`control/config.txt:230`); alcanzabilidad dentro del mapa por `tables/portalsLOS.txt` (`CalcMapRoute.pm:671`); `routeWeights` NPC/WARPITEM para penalizar warps con diálogo (`:131-138`) |
| Evitar mapas peligrosos (propuesta `avoid` tras la muerte por el Vocal) | Diseño pendiente: parámetro `avoid` en Perl y Python más reinicio del cliente | `control/routeweights.txt`: "Using a weight of 10000 makes it pretty sure to completely avoid a map" |
| Elegir monstruo viable | `hunting.viable_targets` y orden por distancia (`solo_cycle.py:543-555`) | `attackAuto` + `mon_control.txt` (columnas `attack`, `lv`, `joblv`, `hp`; `-1` = ignorar aunque ataque) |
| Patrullar o explorar el campo | Candidatos, rayos, bolsas y `walk.explore_cells` (`solo_cycle.py:556-588`, `10425e5`) | `lockMap` + `route_randomWalk` (`config.txt:217-229`) |
| Descansar o retirarse | `recovery_tick` (`m1_bridge.pl:361-412`) | `sitAuto_hp_lower/upper` (`config.txt:290-299`), `runFromTarget` (`:262-269`), `teleportAuto_hp` (`:313`) |
| Vender, comprar y volver | Fases `to_shop`/`sell`/`buy`/`return` (`solo_cycle.py:597-620`), `p2_supply.decide` | `sellAuto`, `buyAuto`, `items_control.txt`, `attackAuto_notWhile_*` (`config.txt:78-79`) |
| Repartir stats y habilidades | `build_policy.py` + `stat_up`/`skill_up` confirmados | `statsAddAuto_list`, `skillsAddAuto_list` (`config.txt:302-308`) |
| Huir de una amenaza concreta | `pack_burst` propuesto (nota de relevo) | `mon_control` `teleport` (distancia o al ser atacado), `teleportAuto_minAggressives`, plugin `avoidAssisters` (en `plugins/`) |

La investigación previa ya lo vio: OpenKore es la *"Primera opción para ejecución
reactiva, navegación, combate y mantenimiento del personaje"*
(`docs/research/BOT_EXECUTION_OPTIONS.md:23`). La razón de `--ai=manual` era
tener un único dueño y resultados veraces. El precio es convertir cada acción
reactiva en una RPC con su contabilidad. Para atacar a un Poring, una acción
idempotente que se corrige sola, esa contabilidad no aporta valor.

**Lo que la IA nativa no resuelve sola [opinión, honesto]:**

- Sus valores por defecto tienen patrones típicos de bot. Hay que variar umbrales, añadir pausas (`autoBreakTime`) y elegir campos con criterio, que es justo lo que aportan el planner y el temperamento.
- Hay que contar kills y muertes desde eventos del puente (paquetes de muerte de actor, EXP, `dead`) en lugar de desde resultados por petición. Es más simple: es observación, no conciliación.
- Para que el planner cambie de campo hacen falta `conf`/`reload` y una forma de saber que la nueva config está activa. Es un único punto de sincronización, en lugar de uno por ataque.
- Los diálogos guionizados (tutorial, Job Changer) y el comercio siguen necesitando el puente actual: eso se conserva.

**Comparación con alternativas:** ver la sección 3.

### 2.3 Plan y ritmo

Datos de `git log` [verificado]:

- 138 commits en 5 días (2026-10-29 → 11-02). Por tipo: `docs` 61 (44 %), `feat` 36, `fix` 25, y el resto, sin prefijo, mezcla arreglos y conciliaciones.
- Desde el 2026-11-01, 43 commits:
  - unos 16 corrigen casos límite: `6302a78`, `eafb4d7`, `83b0f05`, `786ba0b`, `77ce3db`, `9514703`, `f712bf0`, `e574b18`, `80c13c2`, `38034e7`, `eda1a07`, `fae125e`, `569b68f`, `a682e76`, `10425e5` y `6553c7e`;
  - 6 añaden funciones: `d64b41e`, `2d77b4e`, `4b05449`, `d233b46`, `01c4cd5` y `c5b636f`;
  - el resto es documentación.
- El commit más grande del periodo es un **arreglo** (`e574b18`, +1458/−502), que reimplementa la alcanzabilidad que `portalsLOS` ya resuelve.
- Patrón de cada tanda en vivo: unos 870 s, un bloqueo nuevo, un arreglo, otra tanda (`CURRENT_STATE.md:3-31`). Los bloqueos son `travel:failed/unreachable`, `exploration_no_reachable_candidate`, resultado tardío, `travel:failed/died`, el guardián de RAM y el de GPU. Las tasas observadas son de 0,8 a 1,5 kills/min, con 4 viajes de venta en 14,5 min (`docs/evidence/P5-field-by-level.md:62,70`).
- Sobrecarga de proceso:
  - `CURRENT_STATE.md` tiene 382 líneas;
  - `HANDOFF.md` repite su contenido;
  - hay `USER_GUIDE.txt`, un registro de 22 chats en `.ai/chats/`, relevos Codex↔Claude y una sesión por objetivo;
  - el 44 % de los commits es documentación.

  Cada sesión nueva vuelve a derivar el contexto [opinión].

**¿Hay un camino más corto? Sí [opinión]:**

1. Prueba acotada (1–2 días): `--ai=auto` con config generada, en un perfil nuevo (§4, R1).
2. Si la prueba aguanta 1 h sin intervención: dejar de mantener las rutas, la exploración y el abastecimiento propios, y llevar Nilo a Job 10 con ese ejecutor.
3. En paralelo o justo después: un segundo personaje en el mismo campo con chat y grupo (`partyAuto`, `follow` y, si hace falta, `attackAuto_party`), reutilizando la conciliación de comercio de M4.

Se llegaría antes a 2–3 agentes conviviendo que con el plan actual, que pone la prueba larga (paso 6) y la comunidad (paso 7) detrás de Job 10.

### 2.4 Modelos e inferencia

Configuración [verificado, `config/model-roles.json`]:

- `planner`: Groq `openai/gpt-oss-120b` con esquema JSON, `reasoning_effort: medium`, hasta 4096 tokens de salida y prompt de hasta 5000 caracteres. Respaldo: `gemma4:12b` local, con un enfriamiento de 300 s.
- `chat`: `gemma4:12b`, solo local.

**¿Qué decide hoy el planner?** Elige entre ≤6 opciones de campo ya puntuadas y
validadas (`agent/goal_planner.py:273`, `hunting.MAX_OPTIONS`), una build
(`:166`) y un destino (`:341`). La propia evidencia reconoce que "El motivo del
modelo puede citar cifras que no se validan; solo se valida el `field_id`"
(`P5-field-by-level.md:69`).

[Opinión] Para elegir entre opciones ya puntuadas, un `argmax` con temperamento y
desempate con semilla, que ya existe (`hunting.py`, `NEAR_BEST`), da casi lo
mismo sin red ni cuota. El valor diferencial de un modelo de 120B está en lo que
todavía no se usa:

- metas diarias y de vida del personaje;
- interpretar el chat de otros;
- negociar;
- reflexionar sobre la propia historia, al estilo de Generative Agents.

**Coste y límites [verificado en la consola de Groq, 2026-11-02]:** para
`openai/gpt-oss-120b`, 30 RPM, 1K RPD, 8K TPM y 200K TPD, **por organización**.
Estimación [opinión]: con unos 2–4K tokens por llamada (prompt más razonamiento)
caben unas 50–100 llamadas al día **para todos los agentes**. Con 5 agentes y
revisión de campo cada 30 min (48 por agente y día), más las subidas de nivel, la
cuota diaria se agota y el sistema pasa a Gemma `degraded` la mayor parte del
tiempo. La degradación está bien diseñada (`inference/roles.py:83-160`), pero
entonces el planner "inteligente" sería de hecho el 12B local.

**Privacidad [verificado en el diseño]:** a la nube solo van hechos del juego y
el chat no sale del PC. Es correcto. Matiz [opinión]: el chat entre bots no es
privado. Si la GPU limita, puede ir a un modelo en la nube; el chat con
**humanos**, no.

**GPU y RAM compartidas [verificado en la evidencia]:**

- Gemma 4 12B llegó a 11.552 MiB de pico (`P5-model-eval.md`). El techo del proyecto es 14.336 MiB.
- Ya hubo tandas paradas o no lanzadas por otros programas: 15.218 MiB de GPU usada y menos de 2 GiB de RAM libre (`HANDOFF.md:5,36-38`, `CURRENT_STATE.md:21`).
- Un único 12B local atendiendo el chat de 3–5 agentes sirve en serie (una cola, `concurrency 1`). Con conversación en grupo, la latencia se acumula.

[Opinión] Para escalar:

- un modelo de chat más pequeño (4B–8B) como opción por defecto en el chat entre bots, y el 12B solo para conversar con humanos;
- turnos de chat con freno, como `mod-ollama-chat`: profundidad máxima de cadena, bots que solo hablan entre sí si un humano habló hace poco, enfriamientos por bot y por canal.

### 2.5 Robustez, pruebas y operación

**Lo que está bien [verificado]:**

- 253 tests en 34 módulos.
- Los tests de contrato ejecutan el módulo Perl real con estados grabados (`tests/test_p1_navigation.py:9`, `test_p1_combat.py:9`).
- Los runners terminan solos y guardan resumen.
- Hay guardianes de RAM y GPU.
- Nunca se reenvía una acción con resultado incierto.

**Debilidades:**

- **Sin operación larga.**
  - La tanda más larga terminó por el guardián de RAM a los ~410 s de 3600 (`HANDOFF.md:36-38`).
  - Las tandas útiles son de 870 s.
  - Cada bloqueo (`block(...)`, unos 20 motivos en `agent/` y el runner) para al personaje hasta que un humano interviene.
- **La política de fallo es "fail-closed" para todo.** Es correcto para el comercio y lo contrario de lo que necesita la autonomía. Ejemplo: tras morir, el sistema se bloquea (`solo_cycle.py:494-497`) y no existe el camino de reaparecer. Un jugador simplemente reaparece y vuelve.
- **La muerte por el Vocal** (nota de relevo `walk-reachability-handover.md`) muestra dos cosas:
  - el modelo de peligro ignora `NPC_SUMMONSLAVE` y los esbirros. Un modelo propio de daño siempre irá por detrás de los datos del juego. `assess` ignora hit/flee, ASPD, habilidades y elementos (`hunting.py:7-8`);
  - el arreglo propuesto añade otro parámetro a Perl y otro reinicio del cliente. `routeWeights` y `mon_control` resuelven el caso sin código. La defensa más robusta, la que usa un jugador, es reactiva: huir o usar una Fly Wing cuando el daño recibido supera un umbral (`teleportAuto_hp`, `teleportAuto_minAggressives`). Es mejor que predecir todos los peligros.
- **Sin simulador entre las pruebas unitarias y el servidor en vivo.** Cada caso límite nuevo se descubre en una tanda de 15 minutos.
- **Dos runtimes divergentes.** `agent/continuous.py` (M4, tres identidades, `--ai=off`) y `agent/solo_cycle.py` + `scripts/run_p2_cycle.py` (P5, una identidad, `--ai=manual`). La comunidad necesitará uno solo.

### 2.6 Credibilidad y comunidad

Lo que existe [verificado]:

- memoria SQLite por identidad (`agent/memory.py`, 55 líneas);
- diálogo acotado (`agent/dialogue.py`);
- comercio con conciliación (`agent/trade.py`);
- tres identidades en el fixture M4;
- informe de estado determinista (`agent/state_report.py`).

Lo que falta para parecer jugadores [opinión, por orden de impacto]:

1. **Coexistir y hablar en vivo durante el juego real.** El rol `chat` está configurado, pero Nilo no conversa durante el entrenamiento.
2. **Agruparse.** Hace falta formar grupo, seguirse y repartir EXP. OpenKore tiene `partyAuto`, `follow`, `attackAuto_party` y los plugins `busParty`/`busFollow` en `plugins/needs-review`.
3. **Memoria social:** relaciones y hechos sobre otros, con resumen y olvido acotados, como Summarize-and-Forget de Lyfe Agents o las notas puntuadas de `mod-ollama-chat`.
4. **Ritmos humanos:** sesiones con conexión y desconexión, pausas, sentarse a charlar, vender en la ciudad y emoticonos. `autoBreakTime` y los emoticonos de OpenKore cubren parte.
5. **Coherencia entre lo que dice y lo que hace.** Es el motivo del controlador cognitivo de PIANO. Aquí ya existe la base: el chat solo afirma hechos del `state_report`.

¿Escala la arquitectura actual? [opinión]:

- En procesos, sí: un OpenKore por agente cuesta poco y un orquestador puede llevar varias identidades.
- En el modelo de ejecución actual, no: cada agente multiplica los casos límite por acción y las intervenciones. Con 5 agentes a un bloqueo cada 15 min, habría una intervención cada 3 minutos.

### 2.7 Riesgos y deuda técnica principales

1. **Ejecutor duplicado** (rutas, exploración, abastecimiento y peligro propios). Es la mayor deuda, y crece con cada caso límite.
2. **Política de fallo uniforme.** Lo reversible y lo irreversible se tratan igual, y eso impide la autonomía.
3. **Objetivo social sin métricas** y aplazado dos veces. Riesgo de que el proyecto se quede en "bot de grind muy auditado".
4. **Cuota del planner en la nube** para 3–5 agentes (TPD) y dependencia de un nivel gratuito que puede cambiar.
5. **Recursos compartidos.** La GPU y la RAM las ocupan otros programas del usuario y las tandas se cancelan. Hace falta un modo de funcionar sin el 12B: planner determinista y chat pequeño.
6. **Coste de proceso:** documentación y relevos (44 % de los commits), varias sesiones con contexto repetido y relevos Codex↔Claude.
7. **Dos runtimes** (M4 continuo y P5) y tres checkouts y ramas (`m3-worktree`, `m4-worktree`, `m4-field`, más la raíz con trabajo pendiente).
8. **Repositorio público.** `sebargith/RagnarokOnline-simulated-population` aparece en buscadores [verificado en la búsqueda]. No se encontraron secretos en esta revisión, que no fue una auditoría. Conviene revisar que las rutas locales, las cuentas de prueba y los registros versionados no expongan nada.
9. **Licencias.** OpenKore es GPLv2; Population Engine, GPLv3 [reportado]. Hay que tenerlo en cuenta si se copia código.

---

## 3. Comparación con alternativas

| Alternativa | Qué es | Encaje con el objetivo | Veredicto |
| --- | --- | --- | --- |
| **Actual**: OpenKore `--ai=manual` y política por acción en Python | Ejecución nativa de bajo nivel y lógica de alto nivel propia | Veraz y auditable, pero lento de construir y frágil en operación larga | **Cambiar** la granularidad |
| **OpenKore `ai=auto` y config generada por la política** (propuesta) | Python y el LLM escriben la config de cada macro-meta y OpenKore ejecuta | Reutiliza 20 años de bot; el puente queda para observación y acciones irreversibles | **Probar ya** (R1) |
| `macro` / `eventMacro` | Reglas por evento dentro de OpenKore | Útil para ganchos pequeños (p. ej., reaparecer y volver); frágil como lógica principal y difícil de probar | **Usar puntualmente** |
| [openkore-ai-v3](https://github.com/iskandarsulaili/openkore-ai-v3) | Fork con sidecar FastAPI, reflejos → heurística → LLM, CrewAI | "Experimental"; 9 estrellas; >100 endpoints [reportado]. El diseño en 3 niveles es una buena referencia; el fork, no | **No adoptar**, solo como referencia |
| [openkore-mcp](https://github.com/diviatrix/openkore-mcp) | Plugin MCP que ejecuta comandos de OpenKore | Prueba de concepto; da autoridad general de consola al modelo | **No** |
| [ragnarokoffline.app, PR #193](https://github.com/Flux159/ragnarokoffline.app/pull/193) (fusionado 2026-09-30) | 1–4 agentes externos (MCP/CLI) que manejan el cliente gráfico Electron | El LLM actúa paso a paso; las cuentas tienen `@warp`/`@go` | **Referencia** de interfaz; filosofía opuesta |
| Botting por memoria o píxeles del cliente | Leer y escribir el cliente gráfico | Más frágil y pesado que OpenKore sin interfaz; necesita cliente y assets | **No** |
| Bots del lado del servidor ([Population Engine](https://github.com/YlenXWalker/Population-Engine), análogo de [mod-playerbots](https://github.com/AthenaSui/mod-playerbots) en WoW) | Jugadores virtuales dentro del emulador | Escala a cientos o miles; menos fieles (recursos virtuales). Sería legítimo, porque el servidor es propio | **Futuro**, para población ambiental, no para los 3–5 núcleo |
| [mod-ollama-chat](https://github.com/DustinHendrickson/mod-ollama-chat) (AzerothCore) | Chat LLM para playerbots: personalidades, memoria resumida, frenos de conversación | El ecosistema maduro más cercano a "bots creíbles con chat"; 139 estrellas [verificado] | **Copiar ideas** de diseño del chat |
| [mod-ollama-bot-buddy](https://github.com/DustinHendrickson/mod-ollama-bot-buddy) | El LLM elige una acción cada pocos segundos | "NOT FOR GENERAL USE YET" [verificado]; muestra por qué el LLM no debe hacer control fino | **Contraejemplo** |
| [Voyager](https://arxiv.org/abs/2305.16291) / Mineflayer (2023) | El LLM escribe código de habilidades sobre una API de bot | Su "biblioteca de habilidades" equivale aquí a configs y capacidades de OpenKore; generar código choca con la frontera de seguridad del proyecto | **Idea sí, mecanismo no** |
| [Mindcraft / MineCollab](https://arxiv.org/abs/2504.17950) (NeurIPS 2025) | LLMs con 47 herramientas en Minecraft, colaboración | Hallazgo: el cuello de botella es comunicarse con eficiencia en lenguaje natural [reportado] | Avisa de que la capa social es lo difícil |
| [Generative Agents](https://arxiv.org/abs/2304.03442) (UIST 2023) | Flujo de memoria, reflexión y planificación | La ablación muestra que cada parte aporta credibilidad [reportado]; evaluación sobre todo cualitativa (PREreview) | **Adoptar** reflexión y planes diarios para la capa social |
| [Lyfe Agents](https://arxiv.org/abs/2310.02172) (2023) | Opción-acción, Summarize-and-Forget, coste 10–100× menor [reportado] | Es justo el patrón "LLM poco frecuente sobre opciones" | **Alineado**; usar su memoria |
| [Project Sid / PIANO](https://arxiv.org/abs/2411.00114) (2024) | De 10 a más de 1000 agentes, controlador cognitivo para la coherencia | Escala y coherencia entre habla y acción | Referencia de coherencia; su escala no es el objetivo |
| [rust-ro-bot](https://github.com/pts1667/rust-ro-bot) | GOAP sobre la Bot API de rust-ro | Ya evaluado en `BOT_EXECUTION_OPTIONS.md`; útil solo si la recombinación lo justifica | Sin cambios |

Otros trabajos relacionados: [encuesta de agentes LLM en juegos](https://arxiv.org/abs/2404.02039)
(2024); [economía de MMO con agentes generativos](https://arxiv.org/abs/2506.04699)
(2025: especialización de roles y precios emergentes, solo en simulación); [retos de
los agentes "humanlike"](https://arxiv.org/abs/2505.20011) (AAMAS 2025: distinguir
humanos de bots con datos); y "Claude Plays Pokémon"
([seguimiento con Opus 4.5](https://www.lesswrong.com/posts/gogZyeistdaDFuhbG/claude-plays-pokemon-opus-4-5-follow-up)),
que muestra que la navegación de largo horizonte sigue siendo el punto débil de los
LLM y que el arnés pesa mucho [reportado]. Esto refuerza la decisión del proyecto
de **no** dejar la navegación al LLM.

No encontré otro proyecto público con jugadores IA persistentes y sociales sobre
rAthena con un cliente bot. Lo más cercano es el PR #193 de ragnarokoffline.app,
dirigido por un LLM externo y con comandos de GM. [spike-ro/rathena-AI-world](https://github.com/spike-ro/rathena-AI-world)
se centra en NPC. El nicho es real [opinión].

---

## 4. Recomendaciones priorizadas

### Las 5 principales

**R1 — Prueba de ejecutor nativo (1–2 días, en un perfil nuevo, sin tocar a Nilo).**

- Generar desde la política actual un `config.txt` y un `mon_control.txt` por macro-meta:
  - `lockMap` en el campo elegido y `attackAuto 2`;
  - `mon_control` desde `p5-monsters.json`: `-1` para lo no viable, `lv` como margen y `teleport`/huida para jefes, invocadores y esbirros;
  - `routeWeights` 10000 en los mapas peligrosos;
  - `route_maxWarpFee 0` y `NPC` con peso alto para usar solo portales gratuitos;
  - `sitAuto_hp_lower`, `sellAuto`/`buyAuto` en el Fruit Gardener con umbrales de peso razonables;
  - `statsAddAuto_list`/`skillsAddAuto_list` desde la build.
- El puente solo observa: kills, EXP, muertes, mapa, inventario y nivel. El planner cambia la config al subir de nivel.
- Criterio: 1 h sin intervención, con 0 muertes no recuperadas. Comparar EXP/h y kills/h con las tandas actuales.
- Si pasa, retirar `M1Travel`, `walk`, la exploración, las fases de abastecimiento y `recovery_tick` del camino principal. El puente se conserva para el tutorial, el Job Changer, la compraventa explícita y el comercio.

**R2 — Política de fallo por clase de acción y métrica MTBI.**

- Irreversible (comercio, compraventa, cambio de clase, puntos, scripts NPC): se mantiene la conciliación estricta y el bloqueo.
- Reversible (moverse, atacar, explorar, recoger): sin intención persistente; ante la duda, continuar.
- Muerte: reaparecer, registrar el campo como peligroso y volver a decidir, sin intervención.
- Siguiente puerta de aceptación: **MTBI ≥ 4 h** antes de Job 10 y antes de añadir agentes. Va antes que el "paso 6", no después.

**R3 — Adelantar la comunidad, con métricas.**

- En cuanto R1 o R2 lo permitan: 2 personajes en el mismo campo, con chat local (rol `chat`), grupo (`partyAuto`) y un intercambio real reutilizando `agent/trade.py`.
- Definir ya las métricas sociales y la revisión ciega de §2.1.
- Diseñar el chat con los frenos de `mod-ollama-chat` y la memoria resumida de Lyfe Agents y Generative Agents.

**R4 — Reasignar el LLM a donde aporta.**

- Elección de campo y build: determinista (puntuación con temperamento). El LLM solo decide en empates o en situaciones nuevas, con su motivo validado contra `facts`.
- El planner de 120B, para metas diarias, reflexión, negociación e interpretación social, con un presupuesto por agente y día dentro de 1K RPD / 200K TPD por organización.
- Evaluar un modelo de chat pequeño (4B–8B) para el chat entre bots, de modo que el sistema funcione cuando la GPU esté ocupada.

**R5 — Menos proceso, un solo runtime.**

- `CURRENT_STATE.md` en una página (hoy 382 líneas), un único relevo y evidencia solo al cerrar hitos, no en cada tanda.
- Agrupar los arreglos de casos límite en commits por causa raíz.
- Congelar M4 (`agent/continuous.py`) como regresión y construir la comunidad sobre un único orquestador multiagente.

### Qué mantener, cambiar y abandonar

**Mantener:**

- rAthena pre-Renewal fijado, OpenKore sin interfaz gráfica, Windows nativo;
- el puente con token, épocas y `accepted/completed/unknown` para acciones irreversibles;
- la conciliación del comercio M4 y del cambio de clase;
- el Job Changer propio;
- las tablas generadas desde los datos fijados;
- los temperamentos;
- el registro de decisiones con `facts` y `served_by`;
- el adaptador de roles con respaldo y degradación;
- los principios de privacidad y aislamiento;
- las pruebas de contrato sobre el módulo Perl real.

**Cambiar:**

- la granularidad del ejecutor (R1);
- la política de fallo (R2);
- los criterios de aceptación (MTBI y métricas sociales);
- el papel del LLM en la elección de campo (R4);
- la cadencia de documentación (R5);
- los umbrales de abastecimiento: hoy 5 objetos (`p2_supply.py:21`) y unos 90 s de caza entre viajes; mientras siga el ejecutor actual, decidir por peso y Zeny.

**Abandonar o congelar:**

- el enrutado propio entre mapas y las zonas a pie (`M1Travel::walk_graph/plan`, `agent/walk.py`, `config/walk-zones.json`) como camino principal;
- la exploración y la elección de objetivos en Python;
- las intenciones persistentes por cada kill o recogida;
- el parámetro `avoid` propuesto en Perl (usar `routeWeights`);
- seguir puliendo el modelo de daño propio (usar `mon_control` y la huida reactiva);
- el mantenimiento activo del runtime M4 con fixture;
- más evaluaciones de modelos para el planner antes de que el planner tenga una tarea que lo justifique.

---

## 5. Qué no se verificó

- No ejecuté OpenKore en modo `auto` en este servidor. La tabla de §2.2 se basa en el código fijado y en `control/*.txt`, no en una prueba. En especial, no comprobé:
  - que `CalcMapRoute` con `route_maxWarpFee 0` evite por sí solo todos los warps NPC gratuitos con diálogo (por eso se propone además el peso `NPC`);
  - la precisión de `portalsLOS.txt` en `prt_castle`.
- Las tasas de kills y la mediana de 90 s salen de la evidencia del proyecto y de una constante del código, no de una medición propia.
- La estimación de llamadas por día a Groq depende del tamaño real de los prompts y del razonamiento; es un orden de magnitud.
- Las cifras de proyectos externos (estrellas, escalas, mejoras de coste) son las que muestran sus páginas o artículos en la fecha de consulta.

---

## 6. Fuentes

Consultadas el 2026-11-02 salvo indicación.

**Código local [verificado]:**

- `vendor/openkore` (`e0b04ee70`, 2026-10-20): `src/Task/CalcMapRoute.pm`, `control/config.txt`, `control/routeweights.txt`, `control/mon_control.txt`, `tables/portalsLOS.txt`, `plugins/`.
- Este repositorio en `0acf433`: archivos citados en el texto.

**OpenKore y Ragnarok:**

- OpenKore — <https://github.com/OpenKore/openkore>; wiki `mon_control.txt` — <https://openkore.com/wiki/mon_control.txt>
- openkore-ai-v3 — <https://github.com/iskandarsulaili/openkore-ai-v3> (experimental, 9 estrellas)
- openkore-mcp — <https://github.com/diviatrix/openkore-mcp>
- ragnarokoffline.app PR #193 "Let an AI agent play with me" — <https://github.com/Flux159/ragnarokoffline.app/pull/193> (fusionado 2026-09-30)
- Population Engine — <https://github.com/YlenXWalker/Population-Engine> (32 estrellas, GPL-3.0)
- rathena-AI-world — <https://github.com/spike-ro/rathena-AI-world>
- rust-ro-bot — <https://github.com/pts1667/rust-ro-bot> (ya revisado en `BOT_EXECUTION_OPTIONS.md`)

**Bots de servidor y chat LLM (WoW / AzerothCore):**

- mod-playerbots — <https://github.com/AthenaSui/mod-playerbots>
- mod-ollama-chat — <https://github.com/DustinHendrickson/mod-ollama-chat> (139 estrellas)
- mod-ollama-bot-buddy — <https://github.com/DustinHendrickson/mod-ollama-bot-buddy> (45 estrellas, "NOT FOR GENERAL USE YET")

**Investigación:**

- Park et al., *Generative Agents* (UIST 2023) — <https://arxiv.org/abs/2304.03442>; crítica en PREreview — <https://prereview.org/reviews/17993733>
- Wang et al., *Voyager* (2023) — <https://arxiv.org/abs/2305.16291>
- Kaiya et al., *Lyfe Agents* (2023) — <https://arxiv.org/abs/2310.02172>
- Altera, *Project Sid* (2024) — <https://arxiv.org/abs/2411.00114>
- *Mindcraft / MineCollab* (NeurIPS 2025) — <https://arxiv.org/abs/2504.17950>
- *A Survey on LLM-Based Game Agents* (2024) — <https://arxiv.org/abs/2404.02039>
- *Generative Agent-Based Modeling for MMO economies* (2025) — <https://arxiv.org/abs/2506.04699>
- Świechowski y Ślęzak, *The Many Challenges of Human-Like Agents in Virtual Game Environments* (AAMAS 2025) — <https://arxiv.org/abs/2505.20011>
- *Claude Plays Pokémon: Opus 4.5 follow-up* (LessWrong) — <https://www.lesswrong.com/posts/gogZyeistdaDFuhbG/claude-plays-pokemon-opus-4-5-follow-up>

**Inferencia:**

- Groq, límites de uso — <https://console.groq.com/docs/rate-limits> (`openai/gpt-oss-120b`: 30 RPM, 1K RPD, 8K TPM, 200K TPD; por organización)

---

## 7. Anexo: proyectos adicionales evaluados

Consultas del 2026-11-03, hechas a petición del usuario. Se leyeron páginas
públicas, la API de GitHub y documentos en bruto de los repositorios. No se
instaló ni ejecutó nada. Las estrellas y fechas son las de la API de GitHub en
ese momento.

### 7.1 rdoc — <https://manuuuu21.github.io/rdoc/>

- **Qué es [verificado]:**
  - un sitio estático de **documentación del lenguaje de scripts de rAthena**: comandos y funciones, RID/GID, cómo cargar un NPC en `npc/custom/` y `@loadnpc`/`@reloadnpcfile`;
  - incluye ejemplos con un editor Ace y reglas de resaltado propias (`rathena_highlight_rules.js`);
  - no es un bot ni una base de datos de mecánicas: no trae fórmulas, tablas de monstruos ni mapas.
- **Repositorio:** `manuuuu21/rdoc`, creado el 2025-07-24, último push el 2026-10-30, 2 estrellas y **sin licencia declarada**.
- **Proyectos del mismo autor:**
  - [rAthena-Text-Editor](https://github.com/manuuuu21/rAthena-Text-Editor): editor de scripts sin conexión, GPL-3.0, 4 estrellas;
  - [Ragnarok-Atlast](https://github.com/manuuuu21/Ragnarok-Atlast): buscador local de exportaciones de datos y arte, con importador, extractor GRF y conversor ACT/SPR→GIF; MIT, 3 estrellas, creado el 2026-10-27.
- **Qué aprovechar:**
  - como **referencia humana** al escribir o revisar los NPC propios: el Job Changer (`ARCHITECTURE.md`, "Approved first-job rule") y los scripts de prueba. La referencia oficial sigue siendo `doc/script_commands.txt` del rAthena fijado; rdoc es una versión más legible;
  - Ragnarok-Atlast solo tiene interés para inspeccionar datos a mano; el proyecto ya genera sus tablas desde la base de datos fijada.
- **Qué no adoptar:**
  - nada en tiempo de ejecución. Los agentes no deben leer ni ejecutar scripts de servidor, y los comandos `@` que documenta son de GM, fuera de la frontera de seguridad;
  - sin licencia, no se puede copiar contenido.
- **Encaje con R1–R5:** marginal. Solo sirve como herramienta de desarrollo para los NPC del servidor.

### 7.2 ragnarokoffline.app — <https://github.com/Flux159/ragnarokoffline.app>

**Qué es [verificado]:**

- Una aplicación de escritorio para jugar a RO sin conexión. Electron lanza una microVM (nebula, MIT) con rAthena (fork `Flux159/rathena`) y MariaDB, y el cliente web roBrowserLegacy (fork), con un servidor de recursos en Rust (RemoteClient-Rust).
- Cambia entre Renewal y pre-Renewal con un ajuste ("Game era").
- Prueba los clientes kRO '23 y uno de 2026.
- Datos del repositorio: GPL-3.0, creado el 2026-08-25, último push el 2026-11-02, 192 estrellas, 60 forks, 89 issues abiertas.
- Publica versiones casi a diario: v1.7.5 el 2026-10-28, v1.7.6 el 2026-10-29 y v1.7.7 el 2026-10-31.
- Es un proyecto **muy activo y bastante maduro**, desarrollado en buena parte con agentes de código (tiene `AGENTS.md` y `CLAUDE.md`).

Tiene **tres sistemas de IA distintos**:

1. **Agentes externos** (`electron/AGENT.md`, `agent-api.js`, `agent-driver.js`; el PR #193 del informe):
   - hasta 4 cuentas `aiagent…`, cada una en su ventana del cliente gráfico, manejadas por MCP (`/mcp`, `/mcp/2`…) o por CLI (`ragnarok-agent`);
   - comandos `state`, `walk`, `attack`, `interact`, `dialog`/`choose`, `say`/`whisper`/`party`, `answer`, `skill`, `equip` y entradas de bajo nivel (`click`, `key`);
   - el LLM decide **cada acción**. Las cuentas están en un grupo con `@warp`, `@go` y `@load`, y la guía pide usarlos "cuando de verdad haga falta".
2. **Population Engine**, en una copia propia (`third-party/population-engine/README.md`):
   - "shells" del lado del servidor que caminan, luchan, se sientan, chatean y abren puestos de venta reales; los clientes los ven como jugadores normales;
   - la copia corrige al upstream: interruptor general (`population_engine_enable`, apagado por defecto), población **solo en mapas ocupados**, colores y nombres válidos, y botín recogido;
   - coste medido: ~0,3–0,4 MB por shell. El límite es la CPU del map-server, de un solo hilo: 22–25 % de un núcleo con 1.855 shells y sin jugadores, y prácticamente nada en modo bajo demanda;
   - el upstream fija `PACKETVER 20250716`, y esta copia lo quita para que coincida con el cliente.
3. **Compañeros** (`docs/COMPANIONS.md`, `docs/mods/companion-strategies/`):
   - shells reclutables en un grupo real, entre 4 y 11;
   - siguen a su dueño entre mapas, obedecen modos (`attack`, `def`, `pass`) y roles (`tank`, `supp`, `dd`) por chat de grupo, y su configuración persiste;
   - tienen un **lenguaje declarativo de estrategias** (`db/population_strategy.yml`): reglas con `On:` (eventos como `party_chat` o `party_member_died`), `Requires:` (`Role`, `Skills`, `Items`, `BaseLevel`), `Cast`, `UseItem`, `Equip`, `Leave:` (salir de terreno hostil) y `Sit`. Hay una traza de depuración (`<nombre> trace`). Algunas reglas están "built, not yet played" (`COMPANION_STRATEGY_ROADMAP.md`).

Además, `docs/AGENT_TESTING.md` (`scripts/rotest`) monta un mundo desechable y maneja el cliente real desde la línea de comandos. Distingue "lo que envió el cliente" de "lo que hizo el servidor" con `net(since)`, incluido el código `useskill_fail_cause` cuando se rechaza una habilidad.

**Qué aprovechar:**

| Pieza | Cómo se aprovecha | Encaje |
| --- | --- | --- |
| Population Engine (versión de ragnarokoffline, con interruptor y demanda) | Población de ambiente barata alrededor de los 3–5 agentes núcleo: ciudades con gente, puestos de venta y chat de fondo. Activarla solo en mapas con agentes o con el usuario | Después de R3. Exige verificar con `PACKETVER 20130807` y con OpenKore (que los shells aparezcan como actores normales) y aislarlo con su interruptor. GPL-3.0, compatible con rAthena |
| Lenguaje de estrategias (`On`/`Requires`/`Leave`/`Sit`) | Modelo para el formato de **política como datos** de R1: reglas declarativas y verificables que se traducen a config de OpenKore o a `eventMacro`. `Leave:` es justo la huida de terreno hostil que faltó con el Vocal | R1/R2, como idea de diseño; no se copia código |
| Normas de comportamiento de `AGENT.md` | Base del prompt social: el humano primero, responder por el canal en que te hablaron, una línea cada vez, no tocar su botín ni sus kills | R3 |
| `state` barato con chat y avisos pendientes; `answer yes/no` para invitaciones de grupo | Forma del informe de estado del rol `chat` y de las invitaciones de grupo | R3 |
| `rotest` y `net(since)` | Confirma el diseño `accepted` frente a `completed` del puente. Su idea de **mundo desechable para reproducir fallos** es la pieza intermedia entre las pruebas unitarias y la tanda en vivo que falta (§2.5) | R2/R5 |
| roBrowserLegacy (cliente web, GPL-3.0, 445 estrellas, push del 2026-11-03) | Cliente gráfico para que el **usuario** juegue junto a los agentes y haga la revisión ciega. Hoy el proyecto no tiene cliente humano verificado (README, sección M4). Elige el protocolo por fecha (`PacketVerManager`) [reportado] | R3. Falta verificar que funcione con 20130807 y que los recursos sean legales |

**Qué no adoptar:**

- **El agente LLM paso a paso con `@warp`/`@go`/`@load`.** Contradice la frontera de seguridad: el modelo no toca la consola ni comandos de GM. También contradice el objetivo, que es progreso normal sin recolocaciones (`NATIVE_AGENT_PLAN.md:178-180`). Además, un LLM por acción es lento y caro. Es lo que el informe ya llama contraejemplo.
- **Cambiar de plataforma a ragnarokoffline.app.** Usa clientes kRO 2023/2026 y otro PACKETVER. OpenKore, el ejecutor del proyecto, tendría que soportar ese protocolo, y la microVM con Electron suma piezas que este proyecto no necesita en Windows nativo. El beneficio (instalador y multiplataforma) no responde a ninguna necesidad actual.
- **Los shells como sustitutos de los agentes núcleo.** Tienen recursos y habilidades "virtuales" o facilitados. El propio README cuenta cambios como "Shells pay for their skills" y "A companion lives on its bag" para acercarlos a las reglas, y no progresan como un jugador. Valen como ambiente, no como prueba de autonomía.

### 7.3 Otros proyectos y fuentes nuevos

| Proyecto o fuente | Qué es | Qué aprovechar | Qué no | Licencia | Encaje |
| --- | --- | --- | --- | --- | --- |
| [iRO Wiki Classic](https://irowiki.org/classic/Main_Page) | Wiki de mecánicas **pre-Renewal**: monstruos, mapas, mecánicas de juego, stats, clases y misiones [verificado en la portada] | **Fuente principal de P4:** consultas acotadas a esa wiki, cacheadas con URL y fecha, en lugar de una búsqueda web general. Es MediaWiki, pero no pude verificar la ruta de `api.php` (las rutas probadas daban 301/404) | No tratar su texto como verdad del servidor, que es rAthena con reglas propias (Job Changer) | GFDL 1.3+ "salvo indicación" [verificado] | R4/P4 |
| [RateMyServer, base pre-Renewal](https://ratemyserver.net/) | Base de monstruos, objetos, drops y apariciones por mapa, a tasas 1x | Contraste manual de tablas de apariciones y drops | No extraer datos de forma masiva: la base fijada de rAthena ya es la fuente de verdad del proyecto | Sin licencia de datos clara [opinión] | Solo apoyo |
| [rs-sdk](https://github.com/MaxBittker/rs-sdk) (RuneScape, LostCity) | SDK para agentes de código: servidor propio, cliente sin interfaz "Lite" (~14 MB y 0,4 % de CPU por bot [reportado]) y pasarela | Mismo principio que este proyecto: "high-level bot methods attempt to observe game effects, while low-level sdk.send* methods only confirm … dispatch". Muestra que un SDK de **alto nivel que observa efectos** es la forma usable para agentes, como la de R1. Tiene simulador y tick configurable para pruebas rápidas | No aplica a RO; los agentes escriben código, como en Voyager | MIT, 1.096 estrellas, push del 2026-10-29 | R1/R5, como referencia |
| [OpenMMO Agent UI](https://github.com/OpenMMO-Agent-UI/openmmo-agent-ui), *The Null Epoch*, [Machine-Learning-mmo](https://github.com/killerboyyy777/Machine-Learning-mmo) | MMOs nuevos diseñados para agentes LLM (MCP o JSON por turno) | Confirman la tendencia de exponer el juego como herramientas tipadas | Juegos propios, no RO; prototipos [reportado] | Varias | Ninguno directo |
| [roBrowserLegacy](https://github.com/MrAntares/roBrowserLegacy) | Cliente web de RO | Ver §7.2 | — | GPL-3.0 | R3 |
| [rathena-AI-world](https://github.com/spike-ro/rathena-AI-world) | Fork de rAthena con NPC e historias generados por LLM | Ideas para NPC del mundo, no para jugadores | 4 estrellas y actividad dudosa (la API muestra un push anterior a la fecha de creación) | GPL-3.0 | Ninguno |
| [openkore-mcp](https://github.com/diviatrix/openkore-mcp) / [openkore-ai-v3](https://github.com/iskandarsulaili/openkore-ai-v3) | Ya en §3 | Fechas: openkore-mcp con un solo día de actividad (2026-04-02, 13 estrellas); openkore-ai-v3 con último push el 2026-09-19 (9 estrellas) | — | — | Sin cambios |

Búsquedas sin resultado útil: plugins de bots o "autobattle" para rAthena o
Hercules con LLM, y bots LLM para Ultima Online o Tibia. No se encontró otro
proyecto público de **jugadores** IA persistentes sobre rAthena con un cliente
bot y progreso normal. La conclusión de §3 se mantiene.

### 7.4 ¿Cambia alguna recomendación?

- **R1–R5 mantienen el orden.** Nada de lo revisado ofrece un ejecutor mejor que OpenKore en modo `auto` para el protocolo 20130807. ragnarokoffline.app confirma por otra vía la tesis central: las reglas declarativas de comportamiento (su lenguaje de estrategias) escalan mejor que la lógica por acción, y el LLM paso a paso solo vale como compañero dirigido por un humano.
- **Ajuste a R4/P4 (nuevo):** consultar primero fuentes pre-Renewal concretas, en este orden: la base fijada de rAthena e iRO Wiki Classic con caché y URL. SearXNG queda como respaldo. Se reduce el riesgo de mezclar mecánicas de Renewal, que es la fuente de error más probable en una búsqueda general.
- **Ajuste a R3 (nuevo):**
  - añadir un **cliente humano** (roBrowserLegacy, por verificar) para que el usuario juegue con los agentes y haga la revisión ciega;
  - usar las normas de `AGENT.md` como base del prompt social.
- **Ajuste al futuro (§3, bots del lado del servidor):** Population Engine, en la versión depurada de ragnarokoffline.app, pasa de "futuro" a **candidato concreto** para la población de ambiente, tras R3. Condiciones: probarlo con 20130807 y con OpenKore; mantener el interruptor apagado salvo en mapas con agentes; no contarlo como agente creíble.
- **Lo que el proyecto no debe adoptar:** comandos de GM para agentes, el LLM por acción y el cambio de plataforma o de PACKETVER.

### 7.5 Fuentes del anexo (consultadas el 2026-11-03)

- rdoc — <https://manuuuu21.github.io/rdoc/>; repositorio `manuuuu21/rdoc` en la API de GitHub; [rAthena-Text-Editor](https://github.com/manuuuu21/rAthena-Text-Editor); [Ragnarok-Atlast](https://github.com/manuuuu21/Ragnarok-Atlast)
- ragnarokoffline.app — <https://github.com/Flux159/ragnarokoffline.app>; documentos leídos en bruto de `main`: `electron/AGENT.md`, `docs/COMPANIONS.md`, `docs/COMPANION_STRATEGY_ROADMAP.md`, `docs/AGENT_TESTING.md`, `docs/mods/companion-strategies/reference.md`, `third-party/population-engine/README.md`; versiones v1.7.5–v1.7.7
- Population Engine (upstream) — <https://github.com/YlenXWalker/Population-Engine>; hilo — <https://rathena.org/board/topic/149283-population-engine-advance-fake-players>
- roBrowserLegacy — <https://github.com/MrAntares/roBrowserLegacy>; resumen DeepWiki — <https://deepwiki.com/MrAntares/roBrowserLegacy>
- iRO Wiki Classic — <https://irowiki.org/classic/Main_Page>
- RateMyServer — <https://ratemyserver.net/>
- rs-sdk — <https://github.com/MaxBittker/rs-sdk>
- OpenMMO Agent UI — <https://github.com/OpenMMO-Agent-UI/openmmo-agent-ui>; Machine-Learning-mmo — <https://github.com/killerboyyy777/Machine-Learning-mmo>
- rathena-AI-world — <https://github.com/spike-ro/rathena-AI-world>
