# P2c — uso local de curación, primera entrega

Fecha: 2026-10-31. Base Claude `500b542`; implementación `67c35eb`.
No completa todavía el ciclo individual persistente de P2.

## Comportamiento

- La recuperación nativa puede usar una Apple (512, tipo 0), poseída y sin
  equipar, solo descansando con HP <60 %, vivo, inventario listo, sin amenaza,
  ruta ni tarea activa. No expone comandos libres ni usa inferencia.
- Un paquete por intento. Cooldown de 10 s tras confirmación. El hook propio
  `packet_useitem` debe coincidir en actor, índice y objeto; éxito y reducción
  exacta de una unidad confirman consumo, no una cantidad de HP recuperado.
- Registro persistente previo al paquete junto a bridge.json:
  `healing-state.json`. Pending al reiniciar, timeout de 5 s, discrepancia,
  rechazo o fallo de escritura bloquean nuevos intentos. Se mantiene descanso.
  Conciliar manualmente antes de resolver una incertidumbre; no borrar el
  registro para repetir. No se implementó un reconciliador automático.
- Snapshot y evento `healing` exponen el estado; p1_hunt conserva hasta 32 eventos.
  Su conexión inicial ahora vence a los 15 s.

## Comandos ejecutados y resultados

En D:/Ragnarok Agents/m4-continuous, Python del venv compartido:

- `python -m unittest discover -s tests -p test_p2_healing.py -v`: primer
  intento aislado falló al iniciar Perl con WinError 623; ningún test se ejecutó.
- `python -m unittest discover -s tests -v`, elevado: **81 OK**, 4,840 s.
  Cuatro tests nuevos usan M1Healing.pm real y archivos temporales: admisión,
  confirmación/correlación, cooldown/timeout y persistencia/fallo de escritura.
- `perl -c bridge/openkore/m1_bridge.pl`, con PERL5LIB apuntando a
  vendor/openkore/src, src/deps y bridge/lib: syntax OK (aviso de locale).
- `python -m compileall -q scripts/p1_hunt.py tests/test_p2_healing.py`: OK.
- `python scripts/prepare_p1.py start --runtime 'D:/Ragnarok Agents/runtime'`.
- `python scripts/p1_hunt.py --runtime 'D:/Ragnarok Agents/runtime' --kills 6 --seconds 90`.
- `python scripts/prepare_p1.py stop --runtime 'D:/Ragnarok Agents/runtime'`: Stopped p1-solo.
- `git diff --check`: OK.

## Una ejecución real

Raw ignorado: D:/Ragnarok Agents/runtime/p1/evidence/hunt-1793461320.json
SHA-256: `15cedf667590311ac6a64d46743e7716e526fe1faa1cf7d2fbbfae6c94678fe0`.

91,3 s, tres kills (2 Lunatic y 1 Poring), un Jellopy recogido, cero muertes.
No alcanzó la meta de seis kills antes del límite; terminó descansando.
Apple: pending a 1793461241698 ms y confirmed a 1793461241706 ms,
remaining 0 (antes 1). HP al ack 29/57; después se observó recovered a 52.
No atribuimos toda la diferencia de HP al objeto: la regeneración también existe.
Al final 22/57 HP, nivel base4/job2, prt_fild08 174,246, recuperación rest.
El cliente siguió descansando hasta detenerlo; el HP al cierre no se midió.

No se añadieron recursos ni se modificó HP. Se consumió la Apple que Claude
compró en P2b. No hubo inferencia ni reinicio de servicios o de los tres clientes
m4-field. Antes del arranque solo estaban esos tres clientes; 8770 estaba libre.

## Límites

Solo Apple y descanso sin amenaza. No curación en combate, SP ni habilidades.
Los casos inciertos/rechazados y reinicios están cubiertos con estados del
módulo real; no se inyectaron en el servidor. Queda unir caza y abastecimiento
con checkpoints y conciliación; esta prueba no acredita autonomía prolongada.
