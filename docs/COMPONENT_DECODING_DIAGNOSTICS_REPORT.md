# Contraste de formato y diagnóstico retenido — 2026-10-08

El formato explícito corrige la salida JSON de estos controles, pero **no valida la geometría**. El modelo todavía agrupa ubicaciones y produce contradicciones semánticas. Se incorporó únicamente un adaptador de diagnóstico offline al caller experimental; ninguna observación puede aprobar, rechazar, rescatar o provocar otra generación.

Base de ejecución: `7c1871cdd15fd33050e31fa37a8cdc2cdc5d25d9`, rama `factory/image-model-routing-modernization`. El código ejecutado incluye cambios sin commit respecto a esa base; cada report conserva hashes del harness, módulo, profile y plan. El SHA del checkpoint de cierre se obtiene del historial/origin. No atribuir los resultados a un árbol limpio de la base.

## Contraste con los mismos píxeles, prompt y presupuesto

Se añadió `--unconstrained-output` a `scripts/observe_visual_geometry.py`: elimina únicamente `response_format`. El parser permanece estricto; no se extrae JSON de prosa ni se repara una respuesta. Se registran fingerprints de la request, del prompt y de la misma request sin la restricción. Los hashes demuestran igualdad dentro de cada par; metadata de comparación, labels, roles y cantidades deseadas no se envían al modelo.

Antes de inferencia: 8080 y 8092 cerrados, RAM libre 21,01 GiB, GPU global 797/12288 MiB, utilización 4%, 30°C; Comfy 8188 HTTP 200, cola 0/0; bridge 8090 HTTP 404 (solo liveness). Qwen3.5-9B Q4_K_M/F16 y llama.cpp b11497 ya presentes y verificados por SHA; no descargas. Cada variante usa un servidor 8092 propio recién iniciado, mismas imágenes/orden, temperatura 0, max_tokens 512, timeout 60 s, contexto 8192, slot 1, Flash Attention on, visual tokens 1024–1536 y thinking off.

| Prompt / restricción | Requests reales | Resultado |
|---|---:|---|
| Original / schema | 2 | Taza presente, pero cuatro partes absent; control sin taza correctamente absent. 6,708 y 5,860 s. |
| Original / sin schema | 1 | Describe boca, hueco del asa y contactos superior/inferior, pero usa pseudo-JSON, estado `present` y objetos en locations. JSONDecodeError conservado; 5,943 s. Segundo control no ejecutado por corte ante fallo. |
| Formato explícito / schema | 2 | JSON válido; boca, hueco, borde y un contacto observado. Ausencia correcta. 7,642 y 6,816 s. |
| Formato explícito / sin schema | 2 | Mismos contenidos finales que el par con schema, JSON válido; conserva el contacto agrupado. 7,735 y 6,853 s. |

Raw: [original restringido](validation/component-decoding-constrained-2026-10-08.json), [original sin restricción](validation/component-decoding-unconstrained-2026-10-08.json), [explícito restringido](validation/component-explicit-constrained-2026-10-08.json), [explícito sin restricción](validation/component-explicit-unconstrained-2026-10-08.json). El control de ausencia usa la imagen reloj/llave, no una taza estructuralmente defectuosa.

`--explicit-component-format` añade al prompt los estados, tipos y JSON Schema básico como reglas de formato, sin ejemplo de respuesta ni cantidad esperada. El schema de decodificación V2 y el resto del payload permanecen iguales. Se registra `target-component-prompt-2`; el prompt original sigue siendo el default. La documentación oficial confirma que el schema de decodificación no se inyecta por sí solo en el prompt ([llama.cpp, consultado 2026-10-08](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)).

**Inferencia de estos controles:** la interacción entre instrucción y decodificación afecta a la respuesta original; explicar el formato mejora ambos modos. No demuestra que todas las gramáticas estén libres de problemas ni que Qwen carezca de limitaciones visuales. Una taza y un control de ausencia, sin repeticiones, no proporcionan una tasa de precisión. La unidad “entrada de locations” todavía no coincide necesariamente con una ubicación física.

## Segunda familia: cuatro llaves retenidas

Se probaron cuatro imágenes independientes con profile V2 para abertura del bow, bandas del shaft, recortes del blade y contactos blade/shaft; prompt explícito, schema, ningún dato de la revisión humana. [Plan](validation/key-explicit-component-plan-2026-10-08.json), [profile](validation/key-target-component-v2-profile-2026-10-08.json), [raw](validation/key-explicit-component-observations-2026-10-08.json). Cuatro requests completadas en 8,285 / 8,750 / 9,479 / 9,186 s, stop y cero reasoning. No reintentos.

Todos los inventories reportan una entrada por componente y las tres comparaciones quedan `uncertain` sin hints. Eso **no acredita igualdad geométrica**: dos bandas se describen dentro de una sola entrada en dos imágenes; el candidato Qwen declara `observed` para una abertura mientras su descripción dice que no hay abertura. Son fallos de separación/consistencia semántica que el validador de tipos no demuestra ni corrige mediante palabras del texto.

La [anotación humana A/B/C](validation/visual-geometry-human-review-2026-10-08.json) queda intacta y separada. A: forma conservada con anillos algo mayores; el protocolo no mide tamaños. B: cambio total; el nuevo comparator no produce señal, por lo que falla en priorizar ese defecto conocido. C: no cambio visible; ausencia de hints compatible con esa revisión, sin certificar exactitud. El protocolo legacy detectaba diferencias en B pero también alarmas falsas en C; no se mezclan sus métricas ni se sustituye retroactivamente el resultado anterior. No se pidió otra vez esa revisión.

Total de esta fase: **11 requests VLM sobre imágenes retenidas, 0 imágenes generadas, 0 retries automáticos**, cinco servidores 8092 propios cerrados. Nada modifica modelos, deps, workflows, routing, flags persistidos, Factory o MPT estable.

## Conexión opt-in de diagnóstico en MPT

`app/services/visual_observation_diagnostics.py`, versión `retained-visual-diagnostic-1`, carga exclusivamente un report suministrado y fijado por SHA256. Limita tamaño/filas, rechaza versiones desconocidas y procedencia duplicada o inválida. Nunca sigue las rutas de imagen del report: vincula una observación a los bytes actuales del candidato. No encuentra evidencia cuando los píxeles cambian. No carga modelos, no usa red, no reconfigura servicios.

El store conserva un snapshot y devuelve copias. Lleva raw content, hash del report, hash de imagen y hashes de protocolo/código disponibles. Excluye configuración privada, etiquetas, comparaciones/verdicts y rutas del modelo. Salidas incompletas, reasoning, contenido inválido o incoherente con el inventory guardado quedan unavailable, con raw conservado. `available` significa únicamente disponibilidad del output registrado; no revalida semánticamente cada descripción ni certifica píxeles. Un JSON formalmente válido pero perceptualmente erróneo continúa `uncertain`.

El caller privado `_download_videos_openai_image_on_demand` acepta `visual_observation_store=None`. Solo una inyección explícita activa la lectura; no se añadió flag ni wiring automático del planner/UI. Registra `visual_observation_diagnostic` en source_info y plan_scenes antes de QA, con `candidate_stage=before_semantic_qa`. La persistencia real utiliza el mecanismo existente de precision diagnostics cuando este está habilitado. No se declara una nueva ejecución de vídeo ni escritura de tarea real: los tests del caller simulan generación/render/persistencia y prohíben red. Si QA/retry/grading cambia el candidato, el hash y etapa siguen identificando la observación anterior; no es evidencia del frame final.

El dato no se consulta en selección, retries, gross/temporal/scoped QA ni en el gate de Klein. Mantiene `admission_allowed=false`, `automatic_rejection=false`, `physical_identity_established=false`, `pixel_truth_verified=false`. Errores del diagnóstico no interrumpen ni rescatan una escena. QA pass/fail/uncertain/unavailable conserva exactamente su resultado con diagnóstico válido, fallido, no coincidente o imagen ausente. Un diagnóstico válido sin QA tampoco verifica una escena experimental.

`scripts/replay_visual_observation_diagnostics.py` permite reproducir esa vinculación offline mediante `--report PATH SHA256 --plan PATH --output NUEVO_PATH`, repetible para varios reports. [Replay de las variantes](validation/retained-visual-diagnostic-replay-2026-10-08.json): 4 reports, 8 vinculaciones; el segundo control sin schema original queda sin observación. [Replay de las llaves](validation/key-retained-diagnostic-replay-2026-10-08.json): 4 vinculaciones. Ambos hacen 0 inferencias/generaciones; no reinterpretan el texto como pass.

## Validación y checkpoint

**495 tests +17 subtests aprobados, 1 integración omitida**, exit 0, 18,70 s ([log final](validation/retained-visual-diagnostic-final-tests-2026-10-08.txt)). Incluye los 387 casos históricos del conjunto QA, 35 nuevos del adaptador/caller y 73 de los harnesses experimentales. Es una ejecución nueva sobre este código, no una cifra histórica reutilizada. Warning Starlette/httpx ya existente; no instalación. Los logs enfocados 77, 94 y 125 pasan y corresponden a subconjuntos/revisiones previas de esta fase.

Reproducir desde este worktree, con `MPT_RUN_INTEGRATION_TESTS=0` y `MPT_KLEIN_BRIDGE_BIN=local_image_stack\experiments\bridge\target\debug\klein4b-experimental-bridge.exe`, Python portable `-B -m pytest -q` sobre:

```text
test/test_klein4b_experiment.py test/test_klein4b_graph.py test/test_klein4b_rust_bridge.py
test/services/test_klein4b_mpt.py test/services/test_material_openai_image.py
test/services/test_qwen_quality_v31.py test/services/test_qwen_native_prompt_audit.py
test/services/test_prompt_continuity_hardening.py test/services/test_evidence_hardening.py
test/services/test_evidence_pruning_root_qa.py test/services/test_evidence_semantic_fallback.py
test/services/test_corrective_continuity.py test/services/test_visual_qa.py test/services/test_llm.py
test/services/test_visual_observation_diagnostics.py test/test_visual_geometry_observations.py
test/test_visual_component_observations.py test/test_multimodal_judge_harness.py
test/test_visual_judge_prefill.py test/test_geometry_review_priorities.py
```

[Checks de cierre](validation/component-decoding-diagnostics-closing-checks-2026-10-08.json) registran JSON/hashes, igualdad de payloads dentro de cada contraste, logs, cierre de servidores y stable HEAD/tracked tree. Secret patterns revisados sin imprimir coincidencias; diff revisado antes de commit/push normal. Preservar los assets/runtime/artifacts/logs ignorados al mover o archivar el worktree; los report públicos no contienen sus bytes.

**Siguiente tarea concreta:** diseñar evidencia de ubicaciones con coordenadas y revisión visual offline para comprobar separación real de contactos/bandas; validar sobre los mismos positivos y B antes de ampliar inferencia. Mantener estos fallos y la revisión humana como controles independientes. El juez actual puede aportar diagnóstico, pero no está listo para factual identity/admisión ni prueba completa automática de vídeo; cambiar a otro modelo o descargar nuevos pesos requiere una decisión específica. No solucionar el bloqueo repitiendo generaciones ni reinterpretando prosa favorable.
