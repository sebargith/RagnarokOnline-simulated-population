# P2 — circuito real de caza y abastecimiento

Fecha: 2026-10-31. Base `f2f273c`. Una ejecución real y acotada del mismo
personaje, sin modificar su inventario ni añadir Zeny de forma artificial.

## Resultado

Tarin retomó el objetivo acumulado 8 desde 4 kills. Cazó y recogió botín;
al alcanzar cinco objetos vendibles, decidió abastecerse:

1. Viajó de prt_fild08 a Prontera a pie, llegó a (105,51) junto al NPC;
   sin gasto de viaje y sin MapRoute.
2. Vendió 1 Clover, 3 Jellopy y 1 Chrysalis; inventario y Zeny confirman
   exactamente +18 Zeny (de 10 a 28).
3. Compró 1 Apple por 15; inventario y Zeny confirman Apple +1 y 28→13.
4. Regresó a prt_fild08, posición observada (171,216), junto al destino
   (171,215), por portal y sin gasto de viaje.
5. Continuó la caza hasta 6/8 kills. El runner terminó por su límite de 180 s
   con navigate c_14 pendiente. Una consulta de solo lectura recuperó
   completed/arrived sin reenviarlo; checkpoint activo, sin acción pendiente.

No hubo inferencia ni reinicio de servidor/DB. El cliente P1 se detuvo después
de consultar la ruta; la meta 6/8 queda guardada. La evidencia final de c_14
es (150,251); el último snapshot de estado anterior era (150,260), HP 54/57,
Zeny 13. No confundir esos momentos.

## Verificación

- `run_p2_cycle.py set-goal --target-kills 8`: meta guardada sin borrar historial.
- `prepare_p1.py start`, `run_p2_cycle.py run --seconds 180 --max-actions 20`,
  consulta de resultado con el mismo ID y sesión, `prepare_p1.py stop`.
- 99 tests OK tras corregir el script anterior de tienda: rechazos ya no
  permiten continuar como si una acción hubiese terminado con éxito.
- Rutas en vivo con el puente corregido llegaron, pero no se instrumentó si
  alguna necesitó la espera de cinco segundos; esa rama solo tiene tests.
- Revisión delegada de solo lectura: verificar venta/compra desde deltas exactos,
  retorno confirmado y ninguna repetición de operaciones inciertas.
- El script antiguo de tienda todavía requiere que, si ya se comienza en
  Prontera, el personaje esté junto al NPC; el ciclo persistente sí viaja al NPC.

Archivos congelados fuera de Git:
`runtime/p1/evidence/cycle-supply-1793464803/`.

| Archivo | SHA-256 |
| --- | --- |
| events.jsonl | ff320eda4c7d28bc421ed156457f7287a922603462460fb7f528ef784b87b918 |
| state.json | 1d31fb8a70380ddb0c3198f279fd32391866533726e69fa2ef76f4a0b6f3c99f |
| status.json | ce7953417df7d849f87dcc4820d52e5fd8ed4825eae1a69faaca3bc14b390132 |

El resultado establece este circuito individual en su mapa/tienda de piloto,
no supervivencia general, planes del 9B ni autonomía prolongada.
