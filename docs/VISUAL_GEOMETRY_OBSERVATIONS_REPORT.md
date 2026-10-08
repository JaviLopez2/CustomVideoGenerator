# Observaciones geométricas independientes — 2026-10-08

## Revisión humana recibida

El usuario revisó A/B/C y respondió directamente en el chat. [Anotación humana separada y literal](validation/visual-geometry-human-review-2026-10-08.json), con hashes de los pares. Los párrafos de revisión pendiente más abajo describen el estado previo, ya superado. No se reescribieron labels históricos ni respuestas del modelo, ni se cambió código o routing.

| Par | Observación humana | Contraste con inventarios del modelo |
|---|---|---|
| A | Conserva la forma; anillos ligeramente más grandes | No hay hints: pierde la diferencia leve de tamaño, fuera de los cuatro atributos categóricos actuales |
| B | Cambia totalmente la forma | Hints de presencia distintos aportan una señal compatible con alteración grave; no validan cada descripción del modelo |
| C | Mantiene la llave, sin cambios visibles | Hints de conteos distintos son falsas alarmas respecto a esta revisión; no hubo rechazo automático porque el comparador conserva uncertain |

La revisión confirma la separación entre conservación general y alteración grave en estos tres pares. **A no se convierte en identidad geométrica exacta:** se conserva la diferencia de anillos y queda sin decidir una tolerancia productiva. No exigir al usuario que esa diferencia desaparezca de su anotación para encajar con pass. Tampoco se usan estas tres observaciones para declarar validado todo el dataset16, OCR, continuidad o un umbral.

El inventario independiente resulta más útil para avisos auditables que el verdict directo, pero pierde cambios de tamaño y alucina conteos. La comparación de descripciones/categorías no calibra severidad por sí sola. Siguiente tarea concreta: diseñar una política experimental de avisos que distinga alteraciones estructurales de variaciones leves/observación insuficiente, y comprobarla con controles adicionales antes de cualquier integración. Conservar incertidumbre, OCR y gates deterministas; un acuerdo de atributos no levanta fail-closed factual. No se implementa esa política en este cierre documental.

Registro sobre3d60ade:0 nuevas inferencias/generaciones/tests, solo anotación/docs y validaciones de JSON/hashes/diff/secret patterns. Los69 tests y4 inferencias del texto de abajo siguen siendo resultados históricos de la implementación del observador, no pruebas nuevas de la revisión humana.

Se separó la observación de cada imagen del veredicto. Cuatro inventarios Qwen3.5 completaron, sin timeouts; el comparador experimental conserva `uncertain` y `admission_allowed=false` incluso cuando coinciden. No se integró con MPT ni se activó routing. La revisión humana de tres pares sigue pendiente.

Base ejecutada `ab4b032825223d9411c254c1206895a83e15798e`, worktree experimental limpio al inicio. El usuario abrió los servicios:8080 health200,8090 root404,8188 system_stats200,cola0/0. Había4084MiB globales/5% GPU pero solo6.69GiB RAM libres; se solicitó cierre temporal de8080 y el usuario lo confirmó. Antes de inferencia:783MiB globales/14% GPU/30°C y20.74GiB RAM libre. No se cerró ningún servicio compartido desde el agente.

## Protocolo experimental

Nuevo script [observe_visual_geometry.py](../scripts/observe_visual_geometry.py). Mismos pesos fijados Qwen3.5-9B Q4_K_M/projectorF16, SHA verificados y runtime portátil b11497. Una carga/context8192/slot1,Flash Attention on,reasoningoff,min1024/max1536 tokens visuales,temperatura0,max512 tokens finales,timeout60s. Cada request lleva una sola imagen completa y el target silver key, sin referencia/candidato como rol, labels, cantidad deseada, contrato de aceptación ni solicitud de verdict. No recortes ni cadena conversacional entre imágenes. Imágenes idénticas se deduplican por SHA: cuatro requests cubren dos referencias y tres candidatos porque una referencia es también un candidato de otro par.

Inventarios de cuatro atributos: aperturas, recortes/muescas de borde, anillos/collares y uniones de piezas. Cada uno tiene visibility present/absent/uncertain, count entero/null y descripción breve. Validación rechaza estructuras incompletas, verdict añadido, bool como count, count negativo, absent con count distinto0, present con0 y uncertain con count numérico. Esto detecta contradicciones estructurales; no demuestra que las descripciones sean verdaderas ni detecta todas sus contradicciones semánticas.

[Resultados brutos](validation/visual-geometry-observations-2026-10-08.json), [checks y tiempos](validation/visual-geometry-observations-closing-checks-2026-10-08.json). Requests4.727–6.556s,media5.681s; no compararlos como aceleración de F1/G1 porque cambia la pregunta y la cobertura. No se muestreó picoVRAM en este script. Todos stop y reasoning_content vacío; esto no prueba ausencia de alucinaciones en content. Un fallo abortaría sin retry y sin completar observaciones ausentes.

## Comparación posterior, sin admisión

La comparación determinista solo genera hints de presencia/conteo distinto o evidencia insuficiente; no interpreta el texto libre como verdad ni produce pass/fail. Todos los pares quedan uncertain. Coincidencias no prueban identidad y desacuerdos no prueban defecto. El comparador es una herramienta offline de auditoría, no un gate productivo ni un sistema de veto activado.

| Caso/label histórico del agente | Hints observados | Salida |
|---|---|---|
| valid_cloth_edit / pass | Diferencias de conteo de muescas y collares | uncertain, no admisión |
| continuity_factual_768 / fail | Presencia distinta de agujero y collares | uncertain, no admisión |
| qwen_continuity_factual_768 / pass | Ninguno | uncertain, no admisión |

La observación detecta el agujero físico del negativo sin pedir un veredicto, mientras el positivo Qwen comparte los cuatro atributos de su referencia. Pero la edición válida produce conteos diferentes entre dos imágenes similares, y el negativo declara ausencia de collares pese a que pequeños rebordes pueden ser visibles. No se convierte esta tabla en precisión perfecta: la señal es imperfecta y las etiquetas históricas no son ground truth independiente. No se reescriben labels ni resultados anteriores; ninguna explicación se usa para rescatar un pass.

## Revisión humana y límites

[Tablero A/B/C](VISUAL_GEOMETRY_BLIND_REVIEW.md): pares con archivos neutrales, únicamente imágenes/roles y cambios permitidos. No muestra opiniones del juez ni labels históricos. Las copias PNG son byte-identical y se preservan ignoradas en target/visual-geometry-blind-review-2026-10-08; [provenance/mapping](validation/visual-geometry-blind-review-provenance-2026-10-08.json) se consulta después de revisar. El tablero usa rutas absolutas locales: no es portable en GitHub sin recrear las copias desde los originales. El usuario conoce el contexto previo; no se afirma cegamiento clínico o experimental perfecto. La revisión será humana independiente del modelo, no un nuevo output del mismo juez presentado como anotación independiente.

Se pidió conserva/cambia/dudoso con evidencia breve para cada par. Mientras no llegue esa respuesta, no declarar validada la geometría ni usar los hints para admisión. Siguiente: registrar la revisión por separado, revisar cada diferencia concreta y definir invariantes observables con incertidumbre explícita. Una futura integración opt-in de evidencia/veto requiere un encargo concreto y debe conservar OCR/gates deterministas y fail-closed factual; los inventarios actuales no levantan ese bloqueo.

## Validación y checkpoint

69 tests offline pasan,exit0,2.98s ([log](validation/visual-geometry-observations-tests-2026-10-08.txt)):11 nuevos del inventario/comparador y58 anteriores. Cubren contradicciones, observación insuficiente, provenance y prohibición de admisión incluso con coincidencia. No implican validación perceptual. Cuatro solicitudes visuales nuevas,0 generaciones/descargas/dependencias/workflows/jobs. Servidor8092 propio cerrado;Comfy/bridge vivos,cola0/0;estable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61/tracked tree intacto. Solo script experimental/tests/docs/evidencias, sin código app ni flags persistidos. Checks de hashes/JSON/diff/secret patterns al publicar; obtener SHA final del historial.8080 puede reabrirse una vez terminada esta ejecución, y futuras inferencias necesitan liberar recursos de nuevo.
