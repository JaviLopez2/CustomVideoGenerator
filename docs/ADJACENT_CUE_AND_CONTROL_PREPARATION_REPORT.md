# Par adyacente y controles retenidos — 9–10 de octubre de 2026

Se obtuvo la observación que faltaba del par templado → caliente con dos consultas nuevas, una por candidato. Ambos reportan la pista visible en las dos imágenes; el resultado permanece `uncertain`. La presencia binaria de la pista no demuestra incremento de temperatura ni progresión. No se selecciona ni aprueba un juez.

Base `bace7ab3a0005b3265ed10654de822c2c14500e4`, rama `factory/image-model-routing-modernization`, diez worktrees. Se conservó el archivo de preparación de revisión humana que ya estaba sin seguimiento. Fetch antes del cierre: HEAD/origin sin divergencia, `0/0`. SHA del checkpoint posterior mediante Git/origin. Las fechas de los artifacts iniciados el día 9 se mantienen; el cierre cruza la medianoche de Europe/Madrid.

## Prueba nueva, contexto exacto

[Plan fijado](validation/adjacent-cue-plan-2026-10-09.json), [receta](validation/adjacent-cue-recipe-2026-10-09.py). Máximo dos HTTP de modelo, cero retries/generaciones/descargas. La receta utiliza el prompt/schema/parser, transporte, selección de assets, verificación de runtime y proceso propio publicados, sin modificar esos archivos. Verifica su propio SHA y el plan anterior; reconstruye los cuatro fullframes nativos y deriva el único par nuevo de las fuentes cálida y caliente existentes.

El anterior enviado es `temporal_warm_512`, preparado SHA `dcd9c928c4b24e0f827f8860b0e14ae0507ccb13aab1236942ebff9cfaeba841`; el actual es `mpt_temporal_hot_768`, SHA `cde32ec55bd249ea21acc4f50933c5e4ef58c236bf0002b47f7da84a3b994814`. El raw histórico referencia inicial → caliente sigue siendo otro contexto. No se sustituyen sus bytes ni se reabre la cohorte anterior detenida de Qwen3-VL.

| Candidato existente | Consultas nuevas | Pista anterior → actual | Tiempo local de consulta | Carga/readiness propia |
|---|---:|---|---:|---:|
| Qwen3.5-9B Q4_K_M | 1 | observed → observed | 5,567 s | 4,031 s |
| Qwen3-VL-8B Instruct Q4_K_M | 1 | observed → observed | 5,623 s | 4,041 s |

[Raw Qwen3.5](validation/adjacent-cue-qwen35-2026-10-09.json), [raw Qwen3-VL](validation/adjacent-cue-qwen3vl-2026-10-09.json). Dos respuestas `stop`, reasoning vacío, cero tokens de prefijo cacheados y cero casos omitidos. Ambas cumplen el contrato de presencia/pista y producen `reported_visible_in_both`; identity/state/progression scores separados y null, admisión/rechazo automático false.

Son dos mediciones sobre **un único par de imágenes**, sin gold humano independiente. Las descripciones de anterior/actual son iguales dentro de cada respuesta. El esquema pregunta presencia de la pista, no su intensidad: no acredita aumento/disminución, temperatura física, inmovilidad del líquido, identidad o precisión poblacional. Tampoco permite comparar p95 ni el tiempo del QA completo. La carga no incluye todo el hashing previo de pesos/runtime.

La receta tiene un formato separado de resultados; el adaptador de replay actual aún no lo consume. El hueco de observación está cubierto, pero su incorporación al replay/MPT queda pendiente de un cambio compatible probado. No se altera el loader para aceptar una respuesta que no corresponde al par solicitado.

## Revisión de cantidad preparada, pendiente

[Preparación humana](validation/clock-independent-review-preparation-2026-10-09.json) y [comparación de archivos históricos](validation/clock-count-comparison-preparation-2026-10-10.json). Cuatro originales completos, incorporados byte a byte en el tablero SVG local; verificación de SHA/bytes/orden realizada. Se pidió contar agujas y llaves, admitiendo «incierto», sin mostrar recuentos del modelo ni expectativas en el tablero.

La comparación extrae literalmente cuatro respuestas del QA completo con conteo ciego y dos controles de fullframe de prefill. Son seis registros sobre cuatro imágenes, no seis muestras independientes. Cero consultas nuevas para esta preparación. La selección de imágenes sigue a resultados anteriores y no constituye un muestreo imparcial de precisión general. La respuesta humana continúa pendiente; valores/acuerdo/métricas humanos null. Los labels históricos del asistente y la revisión humana de las llaves A/B/C permanecen intactos. No se publican tasas de acierto derivadas de una anotación que no existe.

## Otra familia: cámara y fotografía

[Auditoría de fuentes](validation/retained-camera-control-audit-2026-10-09.json). Cuatro fuentes del run Factory `f36297f1-5cc4-43bf-8d4a-d6bb8725faef` cotejadas por bytes/SHA con su artifact manifest. El diagnóstico registra escena 3 con el ancla `reference-05.png` y escena 9 con la raíz generada de la fotografía más esa ancla. El campo top-level antiguo de escena 3 apunta a otra referencia; no reemplaza el pack seleccionado. Son relaciones registradas, no captura de los bytes HTTP remotos.

Inspección del asistente: la cámara y su disposición plegable son comparables, con papel añadido; no se establece un negativo de estructura mayor. La fotografía conserva cualitativamente su motivo circular y líneas, con otra perspectiva y borde derecho fuera de cuadro; no se acredita identidad física ni cobertura completa. Etiquetas humanas pendientes.

El ancla contiene ICC/EXIF, orientación 1 y alpha no trivial; el rechazo del helper nativo por perfil se reprodujo. Los candidatos también tienen alpha no trivial. No se elimina el perfil, compone un fondo ni transforma/escribe una fuente. Necesitan preparación explícita de color/alpha/provenance antes de una nueva cohorte de modelo. Cero consultas o generaciones sobre estas imágenes.

## Verificación y cierre

[131 tests existentes pasan](validation/adjacent-cue-focused-tests-2026-10-09.txt), 3,31 s/exit 0, sin avisos: observer/runner de pistas, regiones y preflight. Se ejecutaron antes de inferencia y sus archivos no cambiaron. Verificación CPU de la receta con cero solicitudes, más revisión independiente sin hallazgos. Son pruebas del software reutilizado; no tests de precisión perceptual ni una suite nueva de esta receta experimental.

[Recursos previos](validation/adjacent-cue-resource-preflight-2026-10-09.json): RAM libre 18,19 GiB, GPU 1297/12288 MiB/8%/30 °C, puertos 8080/8092 libres, bridge HTTP404, Comfy HTTP200 y cola 0/0. Ambos modelos/runtime rehasheados antes de sus inicios secuenciales. PID propios 27884 y 23440 cerrados por sus handles; puerto 8092 libre después de cada prueba. [Comprobaciones finales](validation/adjacent-cue-closing-checks-2026-10-10.json) incluyen fuentes/código/PID/servicios/estable. Los logs propios permanecen ignorados en `target/adjacent-cue-qwen35-2026-10-09` y `target/adjacent-cue-qwen3vl-2026-10-09`.

Solo documentación, evidencia y receta local del experimento. Sin cambios de app/modelos/defaults/routing/QA/gates/dependencias/workflows, sin generaciones, descargas, jobs Factory o control de servicios compartidos. La copia estable conserva su rama/HEAD/árbol tracked.

Siguiente: preparar explícitamente las entradas de cámara con su color/alpha y procedencia, extender de forma compatible y probada el replay para el nuevo contexto, y registrar literalmente la revisión de recuentos cuando llegue. La calibración independiente, negativos estructurales válidos y latencia de QA completo siguen pendientes. Objetivo global activo; nada que abrir o aprobar para la preparación CPU siguiente.
