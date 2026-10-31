# P2b — abastecimiento NPC acotado

Fecha: 2026-10-31, Claude. Rama `codex/single-agent-plan` (`4ccd7eb`, `838e2a0`).
Alcance: segunda entrega P2 del [plan](../NATIVE_AGENT_PLAN.md), con el contrato
aprobado por el usuario. No incluye usar consumibles en la recuperación, Kafra o
almacén, comercio entre jugadores ni tiendas de interior.

## Qué se implementó

- `bridge/lib/M1Supply.pm` (contrato puro):
  - `validate_sell`: solo objetos "etc" (tipo 3, botín) sin equipar y en cantidad
    poseída; máx. 8 líneas, sin duplicados. Rechazos `item_not_sellable`,
    `insufficient_amount`, `npc_not_found`, `npc_too_far`, `recovering`, etc.
  - `validate_buy`: `max_zeny` no puede superar el Zeny actual (`insufficient_zeny`).
  - `sell_quote` / `buy_quote`: precios de las listas del servidor; compra con
    total ≤ `max_zeny` y ≤ Zeny, y peso resultante < 50 % (con más se corta la
    regeneración natural). Si falla, no se envía nada (`failed/not_in_store`,
    `over_budget`, `overweight_after_buy`, `not_in_sell_list`).
  - `buy_failure`: códigos del servidor → `failed/server_*`.
  - `reconcile`: `completed/sold|bought` solo si el Zeny y cada objeto cambian
    exactamente lo esperado; si no, `unknown/state_mismatch` con lo observado.
- Puente (`m1_bridge.pl`), perfil nativo: `npc_sell {x, y, items, timeout_s}` y
  `npc_buy {x, y, items, max_zeny, timeout_s}`. Hablar al NPC → lista de venta o
  compra del servidor → un único paquete `sell_bulk`/`buy_bulk` → resultado del
  servidor → conciliación (hasta 2 s para que lleguen Zeny/inventario). Si vence
  el plazo tras enviar el paquete: `unknown/result_not_confirmed`. Si el NPC no
  abre una tienda: `failed/not_a_shop`. El snapshot añade `weight`, `weight_max`,
  y `type`/`equipped` por objeto. La tarea `autotalk` de OpenKore también se
  suprime durante una tienda.
- `scripts/p2_supply.py`: política local, sin modelo. Vende el botín si hay ≥5
  unidades "etc" o peso ≥40 %; quiere ≥1 curación (tipo 0) y compra la más barata
  que permite el Zeny observado tras vender. Tienda conocida: Fruit Gardener
  (`prontera 104,49`, Apple/Banana 15 z, de `npc/merchants/shops.txt`); los precios
  efectivos siempre se releen del servidor. No decide sin inventario observado.

## Comprobaciones ejecutadas

- `perl -c bridge/openkore/m1_bridge.pl`: OK.
- `python -m unittest discover -s tests`: 77 tests OK (68 previos + 9 en
  `tests/test_p2_supply.py`: admisión con el módulo Perl real, cotizaciones con
  presupuesto/peso, códigos del servidor, conciliación y política de necesidad).
- En vivo, con los 3 clientes M4-field activos en 8765–8767 sin tocarlos; sin
  reiniciar servidor ni base:
  `p2_supply.py --runtime 'D:/Ragnarok Agents/runtime' --probe`

Ejecución aceptada (`supply-1793460066.json`, 45,7 s):

| Paso | Resultado | Evidencia |
|---|---|---|
| Decisión | ir | botín 7 ≥ 5; curación 0 < 1; Zeny 0; peso 2,7 % |
| `prt_fild08` 170,365 → `prontera` 104,51 | `completed/arrived` 15,8 s | un salto, Zeny Δ 0 |
| Vender 5 Jellopy + 2 Clover | `completed/sold` | precios del servidor 3 y 5 z; esperado +25 z = observado; servidor OK |
| Vender Knife equipado (prueba) | `rejected/item_not_sellable` | sin paquete |
| Comprar Apple con presupuesto 1025 z (prueba) | `rejected/insufficient_zeny` | sin paquete |
| Comprar 1 Apple, `max_zeny` 15 | `completed/bought` | lista del servidor Apple/Banana 15 z; −15 z y +1 Apple observados |
| Volver a `prt_fild08` 170,365 | `completed/arrived` 15,7 s | un salto, Zeny Δ 0 |

Final: Zeny 0 → 10, inventario Knife y Cotton Shirt (equipados) + 1 Apple, peso
57 → 52. Colas observadas: solo `route` (sin `mapRoute` ni `NPC`). Inferencia:
ninguna llamada. Cliente P1 detenido con `prepare_p1.py stop`.

## Fallo encontrado y corregido

La primera ejecución (`supply-1793459936.json`) decidió con el primer snapshot,
antes de recibir el inventario (`inventory: {}`): no vio botín y no fue a la tienda
(sin efectos en el juego). Ahora `decide` devuelve `inventory_not_observed` sin
inventario y el runner decide con un snapshot posterior a 1,5 s de recibirlo
(equipo y apilables llegan en paquetes distintos).

## Límites

- `server_*`, `not_a_shop`, `not_in_store`, `over_budget`, `overweight_after_buy`,
  `state_mismatch` y `result_not_confirmed` solo se cubren con estados simulados.
- La Apple comprada todavía no se usa: la recuperación sigue siendo descanso.
- La tienda y su catálogo son una entrada fija de la política; el puente solo
  confía en los precios que envía el servidor.
- Sin habilidades Discount/Overcharge; el precio pagado es el que lista el servidor.
