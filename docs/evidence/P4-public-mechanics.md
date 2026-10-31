# P4 — consulta pública inicial

2026-10-31. `inference/mechanics.py` y `scripts/ask_mechanics.py` implementan
una interfaz standalone, sin conexión al runner, memoria ni acciones. El 9B
elige una categoría de una lista cerrada; Python construye una consulta pública
fija con reglas PC clásico/pre-Renewal. Ni pregunta ni datos de juego se envían
al buscador. Solo se admiten fragmentos que mencionan explícitamente el contexto
clásico/pre-Renewal y se excluyen marcadores móviles o Renewal incompatibles;
es un filtro heurístico, no prueba de compatibilidad ni exactitud de la fuente.
La salida conserva URLs, consulta, fecha UTC, reglas y versión; la respuesta
es generada y los fragmentos son afirmaciones externas no verificadas, no hechos
observados ni resultados de acción. Caché en proceso: 32 entradas, 24 horas.
Una sola operación activa por proceso, sin reintentos, una búsqueda como máximo;
se reutilizan límites de tiempo, contexto y tamaño existentes. La caché no persiste
al cerrar el proceso. No hay coordinación de concurrencia entre procesos.

Verificado:

- `python -m unittest tests.test_mechanics tests.test_web_search tests.test_web_turn -v`:
  11 OK; cubre categorías, aislamiento, caché/caducidad, ocupado, fallos y fuentes.
- `python -m unittest discover -s tests -v`: 127 OK.
- `python scripts/ask_mechanics.py 'How does weight affect HP regeneration in classic Ragnarok Online?'`:
  el 9B eligió una categoría y terminó con `SearchUnavailable` y fallback explícito;
  no produjo fuentes ni respuesta factual. Ollama escuchaba en 11434 (PID 25416).
- Docker Desktop existente se intentó iniciar, sin éxito observable: `docker ps -a`
  informó que el pipe Linux no existía; `docker version` quedó esperando y se canceló.
  No había proceso Docker Desktop/backend ni listener 8080 en la comprobación final.
  No se modificaron contenedores ni volúmenes. Su configuración conocida está en
  `D:/Local_AI/Services/WebSearch/searxng`. No se tocaron clientes ni servidor de juego.

Pendiente: restaurar el backend existente y comprobar una búsqueda real con fuentes;
después diseñar integración asíncrona al planner con aislamiento y validación de
herramientas. Esto no demuestra P4 completo ni garantiza que la fuente sea correcta.
