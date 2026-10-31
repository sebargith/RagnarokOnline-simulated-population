# P1b — combate, recogida y recuperación nativos

Fecha: 2026-10-31, Claude. Rama `codex/single-agent-plan`. Completa P1 del
[plan](../NATIVE_AGENT_PLAN.md) sobre el perfil de [P1a](P1a-native-navigation.md).

## Colocación de prueba (decisión del usuario)

En pre-Renewal la zona de entrenamiento no tiene monstruos. Con Tarin
desconectado se cambió solo su posición a `prt_fild08` (150,250) y el punto de
guardado a `prontera` 273,354, el mismo que fija la recepcionista con "Direct
access → Prontera". Sin objetos, Zeny ni experiencia añadidos. Tras la muerte
del run 2 se repitió la misma colocación. Viajar entre mapas queda para P2.

## Qué se implementó

- `attack {target, timeout_s}` y `take {target, timeout_s}` en el perfil nativo,
  ejecutados por las tareas de OpenKore (`attack`, `take`) en `--ai=manual`.
  Admisión en `bridge/lib/M1Combat.pm`: objetivo visible, vivo, a ≤14 celdas,
  sin daño ni ataques de otro jugador (no robar), HP ≥60 %, sin recuperación activa.
- Resultados con evidencia del servidor: `completed/killed` solo si el monstruo
  murió tras daño propio (`killed_by_other` si no); `completed/picked_up` solo con
  la entrada de ese objeto al inventario; `target_lost`, `cannot_reach_or_damage`,
  `item_lost`, `take_gave_up`, `timeout`, `died`, `cancelled`, `retreat_low_hp`.
  `task_progress` a 1 Hz con HP, golpes y daño. `respawn` solo estando muerto.
- Recuperación local sin inferencia (`recovery_tick` + `M1Combat::recovery_step`):
  - combatiendo con HP <35 % o con un agresor a <15 celdas: interrumpe la tarea
    (`failed/retreat_low_hp`) y se aleja 12 celdas; repite tramos mientras siga
    perseguido, hasta 60 s; agotado el presupuesto informa `exhausted`;
  - en reposo con HP <60 %: `rest`; rechaza navegar, atacar o recoger
    (`recovering`) hasta 90 %; se sienta solo con Basic Skill ≥3.
  - Eventos `recovery`, `death`; latencias desde el golpe y desde la
    actualización de HP del servidor.
- Los hooks antiguos (`combat`, `inventory_added`) ya no cierran tareas nativas;
  M1/M4 conservan su contrato de fixture. `cancel` vale para cualquier tarea
  nativa (`no_matching_task` si no coincide). Perfil: `attackChangeTarget 0`,
  `teleportAuto_dropTargetEngaged 0`.
- `scripts/p1_hunt.py`: bucle determinista acotado (monstruo visible más cercano,
  patrulla fija si no hay ninguno, recoge drops junto a la muerte), sin inferencia.

## Comprobaciones

- `perl -c` del plugin y módulos: OK. `unittest discover`: 61 tests OK
  (4 nuevos en `tests/test_p1_combat.py`, con el módulo Perl real).
- En vivo (evidencia en `runtime/p1/evidence/`, fuera de Git):

| Run | Resultado |
|---|---|
| 1 (`hunt-1793456591`) | 3 muertes (Lunatic, 2 Porings), Clover y Jellopy recogidos; retirada real con 6/47 HP, ataque cerrado `failed/retreat_low_hp`; recuperación por subida de nivel, no por regeneración |
| 2 (`hunt-1793456820`) | cancelar ataque → `cancelled`/`attack_cancelled`; `respawn` vivo → `not_dead`; 2 muertes, 2 Jellopy; **muerte** contra Drops (ver abajo); `respawn` → Prontera 273,354 |
| 3 (`hunt-1793457478`, política corregida) | 6/6 muertes, 3 recogidas, 0 muertes propias, nivel base 2→4, job 1→2; `rest` a 29 HP, recuperado a 47 en 52 s por regeneración natural |

- Latencias medidas: de la solicitud al primer golpe propio, 32–3412 ms (incluye
  acercarse andando); de la actualización de HP a la decisión de retirada, 15 ms;
  desde el golpe recibido, 464–667 ms (incluye el retraso de daño del servidor).
- Inferencia: ninguna llamada. Un solo ejecutor: OpenKore manual vía puente.
- "M4 Poring" es la etiqueta que la caché compartida `tables/monsters.txt` da a la
  especie 1002; eran Porings normales de `prt_fild08` (el fixture con recompensa
  solo existe en Prontera). No se editó la caché compartida.

## Fallo encontrado: muerte del run 2

Un golpe de Drops (7–8 de 47 HP) dejó a Tarin en 6 HP sin cruzar antes el umbral
de 25 %. La retirada (15 ms tras el HP) hizo 3 tramos de 10 celdas en 4,4 s; el
Drops seguía visible, se agotó el límite por número de tramos y Tarin se quedó
quieto 8 s hasta que el Drops (400 ms/celda frente a 150) lo alcanzó. Corrección:
umbrales 60/35 %, amenaza = agresor a <15 celdas, tramos de 12 mientras persiga,
presupuesto de 60 s. El caso es una regresión en `test_recovery_policy`.

## Límites

- Retirada con la política corregida: solo con estados simulados; el run 3 no
  llegó a HP bajo en combate. [por verificar] en vivo.
- `target_engaged_by_other`, `killed_by_other`, `item_lost` y desconexión: solo simulados.
- Selección de objetivo sin conocer su peligro (solo distancia); sin pociones ni
  sentarse aún (Basic Skill 0). Un `navigate` a un monstruo terminó
  `unknown/route_ended_off_target`, informado como tal.
