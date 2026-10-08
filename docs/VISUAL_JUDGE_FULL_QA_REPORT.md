# Contrato visual completo y geometría factual — 2026-10-08

**Qwen3.5 mejora el conteo ciego, pero todavía no es un gate fiable para identidad/geometría factual.** En16 casos con contrato completo detecta5/6 defectos, acepta9/9 positivos y omite una llave alterada. Un diagnóstico por componentes detecta esa llave, pero rechaza también dos positivos. No se activó integración, routing ni admisión.

Base ejecutada06246184eaba9d676706b341b9e3423466e8a709; branch factory/image-model-routing-modernization. Solo documentación y evidencia nuevas, sin editar el evaluador ni código productivo. Mismos pesos Qwen3.5-9B Q4_K_M/F16 verificados por SHA y runtime portátil b11497/ff30363a0. El usuario mantuvo8080 cerrado tras cerrar el juego en la fase anterior. Antes de ejecutar:1022–1026MiB globales,27–30% GPU,31–32°C,Comfy queue0/0. Hay actividad de escritorio; no es una medición con GPU exclusivamente dedicada. No se observó la saturación/temperatura de la partida anterior.

## F1: contrato completo con cantidades ocultas

[Resultados brutos](validation/visual-judge-full-blind-contract-2026-10-08.json).16 requests únicos en una carga, originales completos y referencias ordenadas, sin ROI. Solo se ocultan expected_count/tolerance y se pide contar todos los componentes independientemente del rol convencional; labels/reviews no se envían. JSON schema estricto top-level sin límites de longitud en reason, reasoningoff, temperatura0,context8192,una slot,Flash Attention on,min1024/max1536 image tokens,768 tokens finales,60s timeout. Código/hashes iguales al checkpoint; el JSON usa evaluation_version4 por la opción unbounded-schema-strings, pero NO es el antiguo V4 con ROI: las políticas deben compararse campo a campo.

TP5/TN9/FP0/FN1 con defecto como clase positiva.0unavailable/0uncertain emitidos; frío esperado uncertain queda excluido de la matriz binaria aunque el modelo volvió a marcarfail. Media9.125s/mediana9.309s; no mezclar con V2 ni atribuir toda la diferencia de tiempo al conteo ciego: recursos, instrucciones y estado de caché difieren. Tokens finales,load_seconds y tiempos individuales se conservan en JSON. Peakglobal7505MiB muestreado cada1s; incluye otras apps, no asignación del modelo ni garantía para concurrencia.

| Caso | Label original | Resultado | HTTP |
|---|---|---|---:|
| temporal_warm_512 | pass | pass | 8.916s |
| unrequested_text | fail | fail | 6.271s |
| valid_cloth_edit | pass | pass | 10.949s |
| identity_style_unframed_512 | pass | pass | 11.502s |
| identity_style_768 | pass | pass | 11.453s |
| style_identity_reversed_768 | pass | pass | 12.211s |
| continuity_factual_768 | fail | pass | 9.012s |
| mpt_t2i_text_contract_768 | fail | fail | 5.787s |
| mpt_temporal_hot_768 | pass | pass | 9.213s |
| mpt_temporal_cooled_768 | uncertain | fail | 11.715s |
| mpt_fallback_identity_style_seed43 | fail | fail | 11.461s |
| mpt_explicit_quantity_seed43 | fail | fail | 11.531s |
| z_image_t2i_768 | fail | fail | 5.820s |
| qwen_continuity_factual_768 | pass | pass | 9.404s |
| root_mug | pass | pass | 3.380s |
| valid_mug_recolor | pass | pass | 7.368s |

El MPT tres-agujas ahora reporta3 y falla por cardinalidad. La llave factual Klein siguepass: la razón enumera piezas convencionales y afirma match sin comparar los rasgos visibles. El positivo Qwen siguepass. En texto prohibido se repite la marca alucinada JAEGER-LECOULTRE frente al LONGINER observado/OCR anterior: verdict fail correcto no valida la transcripción. La identidad temporal se justifica a veces por ser una taza roja, insuficiente para demostrar misma instancia física. No asumir calibración de scores1.0.

## G1: componentes observables, protocolo separado

Se añadieron al contrato de tres casos instrucciones genéricas para comparar aperturas, contornos, protrusiones/muescas, conexiones y posiciones relativas, describiendo referencia y candidato por separado y admitiendo uncertain ante detalle insuficiente. No se indicó dónde estaba el defecto ni se cambió ninguna etiqueta/imagen/referencia. [Dataset derivado con provenance](validation/visual-judge-geometry-component-dataset-2026-10-08.json), [respuestas](validation/visual-judge-geometry-component-results-2026-10-08.json). Fue una carga nueva,3 requests sin retries, misma política queF1. Esto amplía los requisitos: no es una validación independiente ni una corrección retrospectiva deF1.

| Caso | Original | Geometría | Texto | Verdict total |
|---|---|---|---|---|
| valid_cloth_edit | pass | pass | fail | fail |
| continuity_factual_768 | fail | fail | no requerido | fail |
| qwen_continuity_factual_768 | pass | fail | no requerido | fail |

El total daTP1/TN0/FP2/FN0; geometría por separado daTP1/TN1/FP1/FN0 sobre estos mismos labels (análisis derivado, no otro experimento). No contar ambos análisis como muestras independientes. Media11.626s,peakglobal7460MiB. Todas las respuestasstop,reasoning_content vacío,0timeouts.

El negativo ahora reconoce la pieza plana con agujero y diferencias de perfil, aunque nombra imprecisamente partes de la referencia. El positivo Qwen es rechazado por supuesto eje liso/no segmentado pese a que la imagen muestra un collar visible. Hace falta adjudicación independiente del detalle antes de resolver cualquier discrepancia del label previo; se conserva pass como label original, no se cambia para favorecer al modelo.

La edición válida tiene geometrypass y textfail, pero el reason dice explícitamente que no hay texto y que quitarlo es permitido, y se autocorrige varias veces hacia cumplimiento. Se conserva el fail declarado: no se rescata por escoger una frase de la explicación. Reasoning_content vacío tampoco garantiza que el campo reason no incluya deliberación. La explicación contradictoria es evidencia de fallo del judge, no un defecto visual demostrado.

La inspección directa del agente comparó las tres imágenes originales con la referencia. Los labels siguen siendo revisiones previas del agente, no ground truth humano independiente. Dos positivos/uno negativo no validan una política más estricta ni permiten extrapolar tasas de error.

## Cierre y siguiente paso

[Resumen reproducible](validation/visual-judge-full-qa-metrics-2026-10-08.json), [comprobaciones finales](validation/visual-judge-full-qa-closing-checks-2026-10-08.json).19 solicitudes nuevas de análisis visual (16F1+3G1),0generaciones/descargas/dependencias/workflows/jobs,0retries automáticos. Ambos servidores propios cerrados. Estable conserva6d27ba4963ffe469d635db71eaeec506a8ff4b61 y tracked tree intacto; Comfy/bridge responden,cola0/0. Los58 tests del evaluador son los del checkpoint de preparación; no se reejecutó pytest al cambiar únicamente documentación/datasets. JSON,harness/input hashes,diff y secretos se revisan al publicar. El commit de cierre se obtiene de Git, no por self-reference.

No integrar como aprobación automática ni cambiar modelos para ocultar estos fallos. Siguiente tarea concreta: preparar evidencia geométrica estructurada separando observación de referencia/candidato y verdict; revisar independientemente los positivos/negativo y conservar toda contradicción como incertidumbre o indisponibilidad. Evitar que una explicación genérica equivalga a identidad física. Diseñar después una integración opt-in de evidencia/veto que conserve OCR y gates deterministas, sin usar un pass del VLM para levantar el fail-closed factual. Requiere un encargo de implementación; este cierre solo evalúa y documenta.

El conteo ciego sobre la imagen completa es el protocolo que merece continuar; los recortes aislados siguen desaconsejados por el falso defecto anterior. No se ha probado generalización a imágenes nuevas ni vídeo completo.8080 puede reabrirse ahora; nuevas pruebas necesitan volver a reservar recursos.
