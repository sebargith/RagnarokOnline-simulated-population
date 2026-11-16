# Diseño — equipo, economía y progresión observable

Estado: **propuesta** (2026-11-16, Claude). Nada de esto está implementado. Pendiente de aprobación del usuario.

## Problema

En pre-Renewal, el equipo, los consumibles y las cartas determinan qué se puede cazar. Para un humano,
buena parte llega de la comunidad: mercado, regalos y comercio. Los agentes no tienen esa comunidad
todavía. Hay que decidir de dónde sale su equipo y cómo se comprueba que progresan bien sin él.

Hoy el problema es más simple: **la política R1 nunca mejora el equipo.** `config/r1-policy*.json` fija
el equipo inicial (Tarin `[1201, 2301]`, Nilo `[1201, 2305]`: Knife con Cotton Shirt o Adventurer's Suit).
Las reglas solo venden botín y compran Apple y Fly Wing. Nilo tiene 5 495 Zeny y sigue con un Knife.

## Principio

Tres capas de origen, en este orden:

1. **Autosuficiente:** tiendas NPC, botín común vendido al NPC, refinado con mineral comprado al NPC.
   Cubre el equipo básico de las clases 1 hasta ~nivel 40–60, como un jugador solo del RO clásico.
2. **Comunidad de agentes:** botín que otro agente necesita, intercambio, y más adelante tiendas de un Merchant.
   Es el **motivo** del comercio en R3, no un añadido.
3. **Escaso por diseño:** cartas y drops raros (≤ 0,1 %). Con 2–5 agentes casi no aparecen. La progresión
   no debe depender de ellos; se registran como logro cuando ocurren.

Sin comandos @, sin premios y sin spawns, igual que hasta ahora.

## Lo que ya existe y se reutiliza

- `config/p5-equipment.json` (generado por `scripts/build_p5_equipment.py` desde la base fijada de rAthena):
  122 piezas vendidas por NPC, con clase, nivel mínimo, ATK y DEF. **Falta precio, tienda y peso.**
- `agent/build_policy.py::equip_action`: elige la mejor pieza *ya en el inventario* por ranura
  (ATK o DEF), con la misma regla que `M1Progress::validate_equip`. P5 congelado; la lógica es reutilizable.
- `config/p5-builds.json`: build por clase (p. ej. `novice-swordman`).
- Supervisor `run_r1.py` con un punto único de recarga confirmada (`r1_reload`) al subir de nivel.
- Observador `r1_observer` (solo lectura) y comercio conciliado del puente (`agent/trade.py`).

## E1 — Datos de origen

Ampliar el generador de la tabla de equipo, sin editarla a mano:

- precio de compra (`Buy` de `item_db`) y de venta al NPC;
- tiendas y mapa de cada pieza (desde `npc/**/shops.txt`);
- peso, ranuras y nivel de arma (para refinado);
- tabla aparte de botín por monstruo con su probabilidad (`mob_db`), para valorar el botín.

**Aceptación:** tabla regenerada y reproducible; pruebas que comprueban un caso conocido de cada fuente.

## E2 — Mejora de equipo con tiendas NPC (un agente)

Planificador **determinista** (sin LLM) que se ejecuta en los puntos de recarga existentes
(subida de nivel, cambio de clase) y tras vender:

1. Presupuesto = Zeny − reserva (consumibles para una salida: Apple y Fly Wing a su máximo, más un margen).
2. Candidatas = piezas que el personaje puede llevar ahora (clase, nivel, género), vendidas en una
   tienda alcanzable solo por portales gratuitos.
3. Elegir **una sola compra**: la de mayor ganancia por Zeny en la ranura con más diferencia
   (primero arma, luego armadura, escudo, calzado, capa, cabeza).
   Respetar la build: un Swordman de una mano no compra a dos manos si pierde el escudo, salvo que gane más.
4. Registrar la decisión con sus `facts` (Zeny, pieza actual, candidata, ganancia) como ya hace el planner.
5. Botín: no vender piezas que sean mejora para el propio agente (se equipan con la misma regla).

**Ejecución — elegir en una prueba corta (spike):**

- (a) Nativa: el generador emite `buyAuto` de la pieza (máx. 1) y la recarga equipa. **[por verificar]**
  si `buyAuto` maneja bien equipo no apilable y cómo equipar sin el puente (`equipAuto` o comando `eq`
  desde un plugin pequeño `r1_equip` confirmado por el observador).
- (b) Puente: compra y equipa por `m1_bridge` como "compraventa explícita", con conciliación.

Recomendación: (a) si el spike lo confirma, porque mantiene el camino nativo; si no, (b).
Comprar equipo cuesta Zeny pero es recuperable en parte (reventa), así que no exige el bloqueo de lo irreversible.

**Aceptación:** con Nilo, en una tanda de minutos, compra y equipa la mejor pieza asequible
(esperado: un arma de una mano de nivel 1–2 y una protección), con 0 intervenciones y la decisión registrada.

## E3 — Progresión observable

El nivel no basta. El observador y un informe (`run_r1.py report`, nuevo) miden por tanda y por campo:

| Métrica | Qué indica |
|---|---|
| ATK y DEF del equipo puesto (+ refinado) | poder comprado |
| Patrimonio = Zeny + inventario a precio de venta NPC | economía sana |
| Tiempo medio por kill y daño recibido por kill, por monstruo | poder efectivo real |
| Kills/h y EXP/h por campo, muertes y huidas por hora | rendimiento y riesgo |
| Campo actual frente al recomendado para su nivel | si avanza a campos más duros |
| Decisiones de compra con `facts` | si gasta bien (auditable) |

**Referencia empírica, no fórmula:** la revisión desaconseja seguir puliendo un modelo de daño propio.
Se compara el mismo agente en el mismo campo antes y después de cada mejora, y con la tanda R1 de base
(316 kills/h con equipo inicial). Una mejora correcta baja el tiempo por kill o el daño recibido.

**Aceptación:** un informe de una tanda real muestra el antes y el después de una compra en el mismo campo.

## E4 — Refinado (opcional, después de E3)

Solo armas, con Phracon/Emveretarcon comprados al NPC y hasta el límite seguro de su nivel de arma.
Es una apuesta irreversible (puede romper la pieza por encima del límite): va por el puente y nunca
pasa el límite seguro. **[por verificar]** NPC, precios y límites en la base fijada.

## E5 — Economía entre agentes (parte de R3)

- **Lista de deseos** por agente, derivada de su build y del plan de E2 (piezas de otra fuente, botín de misiones).
- **Botín guardado:** cada agente conserva lo que está en la lista de deseos de otro, en vez de venderlo.
  Solo con información que podría saber (lo que el otro dijo en chat o en grupo), nunca leyendo su estado.
- **Oferta en chat** ("tengo X, busco Y") con el rol `chat`; el acuerdo se valida contra el estado real.
- **Intercambio** por el comercio conciliado existente.
- Más adelante, un agente **Merchant** (Discount/Overcharge, tienda) como intermediario.

**Métrica social clave:** cuánto acelera un intercambio la curva de E3 de quien lo recibe,
frente a un agente que no comercia. Así la comunidad se mide por valor, no solo por mensajes.

## Decisión abierta para el usuario

- **Rates del mundo** (EXP y botín para todos, humanos incluidos). Con pocos agentes, los drops raros casi no
  aparecen. Alternativas: rates oficiales y aceptar la escasez, o un multiplicador moderado y declarado.
  Recomendación: decidirlo con datos de E3/E5, no antes.

## Orden y fuera de alcance

Orden: E1 → E2 → E3 → (E4) → E5 dentro de R3. Cada paso, con su prueba corta en vivo; nada de tandas de horas.
Fuera de alcance: cartas y equipo con ranuras como requisito, modelo de daño propio, LLM para elegir equipo.
