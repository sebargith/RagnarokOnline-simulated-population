# Relevo — Ragnarok Agents
Actualizado: 2026-11-01 por Codex. Rama `codex/single-agent-plan`.

## Objetivo y límites
P5.4 incompleto; no iniciar P5.5. Un escritor/runtime. Mantener Groq planner
y Gemma 4 12B respaldo/chat; no alterar personajes ajenos ni recursos.

## Estado verificado
- Recuperación restringida implementada para los dos rechazos de navegación
  de Nilo; conserva historia y exige sesión nueva y observaciones estables.
- Snapshot vivo de Nilo en new_2-2 (100,27), recepcionista visible; recuperación
  registrada en `runtime/p5/cycle/tutorial.json`, sin adelantar paso.
- Muestra 480 s/100 acciones: una acción `npc_script`, opción de entrenamiento
  y warp confirmado a new_1-2 (100,70). Bloqueó `reward_mismatch:receptionist`:
  al warp inventario leído vacío, luego snapshot listo mostró Knife y Cotton
  equipados. No repetir diálogo ni editar el checkpoint; efecto requiere revisión.
- Checkpoint bloqueado paso 1, inflight=null, resultado e historial conservados.
  Nilo detenido tras observar sin petición, tarea ni navegación, con posición
  igual al destino y cola vacía.
- MariaDB y servidores de juego preexistentes siguen activos; Ollama activo.
  No se tocó ningún otro cliente. 215 tests OK. Ver evidencia y estado.
- Siguiente: el chat principal evalúa la discrepancia y solicita aprobación del
  usuario para el siguiente alcance. No asumir P5.4 completo ni iniciar P5.5.
