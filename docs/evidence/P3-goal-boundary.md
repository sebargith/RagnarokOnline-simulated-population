# P3 — objetivos locales del 9B, primera entrega verificada

2026-10-31. Implementación e05d6fc; configuración 9B existente conservada.

## Alcance implementado

Runner acepta --intent opcional. Un servicio BoundedInference, una admisión,
cero reintentos y poll entre actualizaciones. Sin --intent no se crea servicio.
Esquema restringido al estado: meta activa permite continue_current o ask_help
con cantidad cero; meta completada permite hunt de 1..3 adicionales.
La aplicación revalida identidad, percepción fresca, huella del checkpoint
y precondiciones bajo el bloqueo del runner, usando el mismo objeto SoloCycle.
Una respuesta obsoleta no puede sustituir trabajo existente.
No se exponen consola, paquetes, shell, instalaciones ni recursos artificiales.
Estado y eventos registran admisiones, propuesta y resultado. Al agotar acciones,
el runner sigue observando la única inferencia pendiente sin nuevas acciones;
al vencer tiempo registra unfinished. Cierra bridge antes del servicio.

## Verificación real

Modelo instalado y digest verificados mediante /api/tags: Qwen3.5 9B Q6_K
77beda99ef49a70c129557ba3d6a35fc8cb829fce36cfda6f9ea60bb5221ee6f.

Comando final ejecutado desde D:/Ragnarok Agents/m4-continuous, Python compartido:
python scripts/run_p2_cycle.py run --runtime 'D:/Ragnarok Agents/runtime' --seconds 30 --max-actions 1 --intent 'Continue the current goal without replacing it.'

Resultado: action_budget, inference_calls 1, planning_result continued,
goal_kills 8, kills 6, una acción de juego completada, inflight null.
P1 detenido después con prepare_p1.py stop. Checkpoint e inventario reales
preservados. Snapshot final prt_fild08 161,277, HP57/57, Zeny13, base4/job3.
Muestra final: RAM libre10260353024 bytes, GPU9951 MiB; dentro del presupuesto,
sin afirmar capacidad prolongada.

Pruebas iniciales descubrieron dos correcciones:
- Fin por presupuesto de acciones antes de observar el resultado del modelo:
  ahora espera la inferencia dentro del presupuesto temporal.
- El modelo propuso hunt durante meta activa; set_goal era idempotente y
  aparecía goal_saved sin cambiar la meta. Se añadió rechazo explícito y luego
  un esquema que no ofrece hunt en ese estado. Una prueba intermedia confirmó
  rejected y la final confirmó continued. Nunca se sustituyó la meta activa.

El anterior WinError10013 era permiso del sandbox; el acceso autorizado funcionó.
La aprobación de publicación volvió a estar disponible en este turno.

## Pruebas y revisión

python -m unittest discover -s tests: 111 OK, 5,249 s.
12 pruebas de planner incluyen progreso de juego simulado mientras Future sigue
pendiente, stale, fallo de submit, doble aplicación y aplicación bajo lock.
Revisión delegada de solo lectura del bloqueo y condiciones de estado.
git diff --check pasó. No evaluación de naturalidad ni comparación de modelos.

Raw congelado fuera de Git: runtime/p1/evidence/p3-live-1793465840/
(events.jsonl, state.json, status.json). Contiene los intentos iniciales y final.

## Pendientes

La continuación se probó con 9B real; asignar una nueva meta tras completar la
actual se probó con servicio simulado, todavía no en vivo. El fingerprint estricto
puede rechazar propuestas si el gameplay avanza; es esperado y no activa retries.
Faltan objetivos más variados, conversación integrada y P4/SearXNG.
