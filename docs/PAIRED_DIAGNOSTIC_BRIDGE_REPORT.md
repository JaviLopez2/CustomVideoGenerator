# Puente privado de diagnóstico pareado — resultado 2026-10-09

Base `5ad52e072412e16191036a6b5b7121dd93c9619c`, worktree/rama experimental inicialmente limpios y diez worktrees. [Plan](PAIRED_DIAGNOSTIC_BRIDGE_PLAN.md). Se conecta el replay publicado al punto privado de MPT mediante callbacks explícitos; app no importa scripts, carga pesos, configura endpoints o activa defaults.

## Cambio y límites

Nuevo `paired_visual_observation_diagnostics` y dos argumentos privados de `_download_videos_openai_image_on_demand`: `paired_visual_observers` y `scene_paired_observation_contexts`, ambos None por defecto. Con None no hay lectura/hash/callback de diagnóstico. Los contextos no contienen rutas; se usan los inputs reales del caller. Salidas solo uncertain/unavailable, scores separados null, sin admisión/rechazo/verdad física. Campos privados/extra del callback no se copian. Callbacks son código local explícitamente confiado por el experimento, no funciones descubribles por configuración o paths del raw.

Shape recibe el primer input seleccionado, ligado por `comfyui_input` a una ruta local absoluta. El pack preparado incorpora `local_path` por entrada como metadato; el selector, orden y generación no cambian. Un top local_path de una referencia excluida no sirve, ni se inventa carpeta por basename; vínculo ambiguo/ausente deja unavailable. El camino de generación mantiene su raíz estable. Cue recibe la última imagen aceptada/renderizada de la misma clave, no la raíz fija ni una imagen de otra fase. El reset existente limpia ese historial diagnóstico.

Captura pre-QA; finalización tras QA/retries/color grading sin otra consulta. Si falta el resultado final o cambian bytes de candidato/referencia/anterior, las observaciones actuales quedan unavailable y las anteriores se conservan con su etapa. No se usa ningún diagnóstico en selección, retries, presupuestos, QA, `qa_verified` o routing. El store monoimagen y scoped_qa permanecen funcionalmente iguales. Tampoco se afirma que la ruta local demuestre los bytes remotos de Comfy o precisión perceptual.

## Pruebas reales de software

**330 tests y2subtests pasan en25,26s, exit0/sin avisos**, incluidos157 casos nuevos:96 de boundary y61 del caller. [Log final v2](validation/paired-diagnostic-bridge-final-v2-tests-2026-10-09.txt). Ocho archivos relevantes cubren puente, material, continuidad/corrección, diagnóstico monoimagen, QA, Klein y caché. Modelos/HTTP/generación/render sustituidos offline; no GPU/descargas. Las fuentes fijadas permanecen iguales después de este run. La ejecución anterior320+2subtests es histórica respecto de los fixes finales.

RED/GREEN originales:78 fallos de stubs→78pass; caller54fallos/1pass→55pass. Se añadieron12 controles de salida incompleta (RED12/GREEN12),2 de motivo solicitado pero unavailable (RED2/GREEN2), y controles de QA not_required/historial de frame no renderizado. El test de QA usa una observación válida en la segunda escena y prueba que not_required no verifica Klein.

Revisión independiente reprodujo dos P2: referencia del pack excluida usada por el diagnóstico y raw vacío/blanco disponible. Corregidos con bindings por entrada y contenido no vacío; final review no issues. [Review RED](validation/paired-diagnostic-bridge-review-red-tests-2026-10-09.txt), [GREEN final](validation/paired-diagnostic-bridge-review-green-v3-tests-2026-10-09.txt):8pass/149deselected/3,06s. Los dos archivos denominados review-green anteriores contienen7pass/1fail: el fixture environment pretendía recorrer una ruta no primaria que MPT ya suprime. Se comprobó ese selector/binding directamente, sin debilitar la protección ni cambiar routing; ese fallo de fixture no demuestra un fallo del producto. Todos los logs se conservan.

## Demostración CPU con los archivos guardados

[Ejecución fijada](validation/paired-diagnostic-bridge-execution-plan-2026-10-09.json), [receta](validation/paired-diagnostic-bridge-recipe-2026-10-09.py), [resultado](validation/paired-diagnostic-bridge-result-2026-10-09.json), [log](validation/paired-diagnostic-bridge-execution-2026-10-09.txt): exit0, 7,599s de demostración CPU. No es tiempo de juez, QA completo o render real.

Se usan los cuatro stores/archivos reales del replay previo, pero las funciones de generación, upload, QA/runtime y render del caller se sustituyen. Cada cohorte recorre el loop real con y sin inyección, con el mismo resultado y número de llamadas simuladas. Los paths .mp4 son retornos ficticios: se comprueba que no existen archivos de vídeo. **0 nuevas consultas a modelo, imágenes, uploads, vídeos, descargas o control de servicios**. Los logs internos dicen generated/rendered porque recorren el caller simulado; no acreditan una generación real.

| Cohorte | Escenas simuladas por run | Lecturas del store | Diagnósticos finales |
|---|---:|---:|---|
| Cue Qwen3.5 | 4 | 3 | 2 uncertain /2 unavailable |
| Cue Qwen3-VL | 4 | 3 | 4 unavailable |
| Forma Qwen3.5 | 2 | 1 | 1 uncertain /1 unavailable |
| Forma Qwen3-VL | 2 | 1 | 1 uncertain /1 unavailable |

Son12escenas distintas por recorrido y8lecturas retenidas,4uncertain/8unavailable. No confundir con14contextos/11raw del replay anterior: aquí faltan antecedente/referencia en la primera escena y se omite un self-control de forma del recorrido. Además, el raw caliente compara baseline→hot; el anterior real en el recorrido es warm. No se reutiliza esa observación como warm→hot. Qwen3-VL conserva sus casos no ejecutados sin rellenarlos. Los resultados/supuestos del QA simulado no son labels humanos ni tasas de acierto; no se escoge juez.

## Cierre y siguiente tarea

[Checks](validation/paired-diagnostic-bridge-closing-checks-2026-10-09.json). Commit/push normal exclusivamente en rama experimental, SHA de cierre mediante Git/origin. MPT estable/main, modelos, dependencias, workflows, defaults y datos humanos históricos protegidos.

Siguiente: preparar controles perceptuales de otra familia con imágenes ya guardadas, separando cantidad/partes/forma y estado; registrar exactamente los pares adyacentes que faltan y las anotaciones independientes necesarias antes de una cohorte acotada. No repetir la microedición de taza cerrada ni atribuir gold al asistente. La selección necesita sensibilidad/error/abstención y latencia de QA completo; la integración de diagnóstico ya funciona, pero no satisface esa validación. Objetivo global activo, sin routing automático ni intervención rutinaria para preparación CPU.
