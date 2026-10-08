# Comparación local de jueces visuales — 2026-10-08

**Selección para continuar en experimental: Qwen3.5-9B Q4_K_M con projector F16.** En el protocolo base detectó4/6 defectos y aceptó9/9 positivos; Qwen3-VL-8B-Instruct detectó0/6 y tuvo tres timeouts. Qwen3.5 no está validado como gate automático: aceptó una llave deformada y un reloj de tres agujas. No se cambió routing ni producción.

## Entorno y alcance

Base de ejecución `8ebbb17480f07dd6235ff9b66a65d7dc2a3edbe7`, rama `factory/image-model-routing-modernization`, worktree Windows experimental limpio inicialmente. Código del evaluador corregido durante la prueba y versionado al cierre. Fetch0/0. El campo base_head de los JSON iniciales procede del manifiesto de assets (`b97ec8c`), **no es el HEAD del código ejecutado**; los reportes posteriores registran execution_head/harness_sha256. Estable protegido HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61.

Checkpoint del evaluador/tests final: `0452649be06b8a17cb269f4f0d62fbf94bc2be71`. El commit posterior reúne matriz/evidencias y handoffs; recuperar su SHA con `git log -1 -- docs/VISUAL_JUDGE_COMPARISON_REPORT.md`.

Usuario autorizó descargas y evaluación GPU y cerró personalmente el servidor8080. Baseline inicial GPU4425/12288MiB tras ese cierre; otros procesos/desktop permanecieron. Cola Comfy vacía. El agente lanzó exclusivamente servidores temporales8092 y cerró cada PID propio en finally. No se cerró/reconfiguró Comfy ni bridge. No se reinició8080 automáticamente.

RTX3060 12GB, driver617.14, runtime oficial portátil llama.cpp b11497/ff30363a0, CUDA12.4. Cuatro GGUFs y ZIPs de runtime con hashes verificados; [provenance](validation/visual-judge-candidates-assets-2026-10-08.json), [descargas](validation/visual-judge-download-verification-2026-10-08.json). Pesos/ZIPs/logs/crops ignorados bajo target: preservar antes de archivar. Ambos modelos Apache2.0;8B desde Qwen oficial y9B desde conversión Unsloth del modelo original, sin fine-tune.

## Protocolos y fallos del evaluador

Dataset:16 artifacts existentes,9 positivos,6 negativos y1 frío incierto. Labels de revisión visual previa del agente, no adjudicación humana independiente; no se modificaron para favorecer modelos. Cero imágenes generadas o vídeos. Los recortes diagnósticos son derivados de imágenes existentes, no generaciones.

**V1:** JSONobject, reasoningoff, context8192, tokens768, timeout60s, max1536 image tokens, sin Flash Attention explícita. Dos solicitudes8B alcanzaron60s sin respuesta; el snapshot observado seguía en prefill con0 tokens generados.9B respondió17,207s y29,854s, sin reasoning, pero el parser rechazó campos temporal/forbid_text anidados. Fallo de contrato del evaluador, no prueba de visión unavailable. [Registro original](validation/visual-judge-comparison-2026-10-08.json). [Reparseo offline](validation/visual-judge-schema-diagnosis-2026-10-08.json): temporal pass y texto fail, sin ninguna nueva inferencia. No se reescribieron resultados originales.

**V2 base:** esquema JSON estricto con campos top-level; conteo se decide por observed_count contra el contrato, no por un verdict declarado. Flash Attention on, min1024/max1536 tokens por imagen para preservar detalle/grounding, GPU layers99 solicitadas, una slot/context8192, temperatura0, reasoningoff, máximo768 tokens, timeout60s. Mismas condiciones para ambos. No se demuestra causalidad aislada de Flash Attention: cambiaron esquema y límites visuales simultáneamente. Los modelos declaran vision=true y se observó actividad GPU; el número configurado de capas no sustituye a una auditoría de buffers por capa.

Cada modelo tuvo16 intentos únicos.8B se detuvo tras dos fallos temporales consecutivos; después se ejecutaron exclusivamente sus seis casos aún no intentados, sin repetir timeouts.9B completó16 en una carga. [V2 principal](validation/visual-judge-comparison-v2-2026-10-08.json), [seis pendientes8B](validation/visual-judge-comparison-v2-remaining-2026-10-08.json). Cargas se registran aparte; la media de requests incluye prefill visual y generación de respuesta, no descarga/carga de pesos.8B incluye dos sesiones, por lo que el estado de caché/cold-start no está perfectamente emparejado.0 retries de inferencia por caso dentro de cada protocolo.

**V3 diagnóstico separado:** cinco casos (3 negativos/2 positivos), cantidades objetivo/tolerancias ocultas al modelo, instrucción de contar todos los componentes visibles independientemente de su papel convencional, recortes suplementarios basados en grounding/OD Florence ya registrados, razones acotadas a120 caracteres mediante schema. Se mantienen imágenes completas/referencias. No es una ablación de un solo factor, ni se mezcla con las métricas V2. [Bboxes y hashes](validation/visual-judge-region-provenance-2026-10-08.json), [protocolo/respuestas](validation/visual-judge-count-roi-probe-2026-10-08.json).

## Matriz base V2

| Caso | Esperado | Qwen3-VL8B | Tiempo8B | Qwen3.5-9B | Tiempo9B |
|---|---|---|---:|---|---:|
| temporal_warm_512 | pass | unavailable | 60.017s | pass | 29.477s |
| unrequested_text | fail | pass | 15.898s | fail | 19.318s |
| valid_cloth_edit | pass | pass | 28.195s | pass | 33.070s |
| identity_style_unframed_512 | pass | pass | 32.229s | pass | 34.714s |
| identity_style_768 | pass | pass | 32.653s | pass | 35.677s |
| style_identity_reversed_768 | pass | pass | 33.078s | pass | 34.952s |
| continuity_factual_768 | fail | pass | 30.099s | pass | 28.310s |
| mpt_t2i_text_contract_768 | fail | pass | 14.610s | pass | 17.746s |
| mpt_temporal_hot_768 | pass | unavailable | 60.013s | pass | 28.722s |
| mpt_temporal_cooled_768 | uncertain | unavailable | 60.017s | fail | 34.556s |
| mpt_fallback_identity_style_seed43 | fail | pass | 33.163s | fail | 34.939s |
| mpt_explicit_quantity_seed43 | fail | pass | 32.684s | fail | 35.383s |
| z_image_t2i_768 | fail | pass | 15.137s | fail | 17.499s |
| qwen_continuity_factual_768 | pass | pass | 28.929s | pass | 28.304s |
| root_mug | pass | pass | 8.492s | pass | 10.064s |
| valid_mug_recolor | pass | pass | 20.254s | pass | 21.853s |

| Métrica preliminar | Qwen3-VL 8B | Qwen3.5 9B |
|---|---:|---:|
| Defectos detectados / seis | 0/6 | 4/6 |
| Defectos aceptados erróneamente (FN) | 6 | 2 |
| Positivos aceptados (TN) | 7/9 | 9/9 |
| Positivos rechazados (FP) | 0 | 0 |
| Unavailable | 3 | 0 |
| Uncertain emitidos | 0 | 0 |
| Media / mediana | 31,592 /31,164s | 27,786 /29,099s |
| Máximo | 60,017s | 35,677s |
| Pico global VRAM muestreado | 11299MiB | 10448MiB |

[Cálculo reproducible y sources](validation/visual-judge-baseline-metrics-2026-10-08.json). Cold-state expected uncertain excluido de TP/TN/FP/FN:8B unavailable,9B fail. No se acredita ese fail como defecto demostrado. No p95 con16 muestras. Los FP/FN se definen con defecto como clase positiva; indisponibilidad se informa aparte. Los ceros FP no son prueba estadística de ausencia de falsos rechazos.

VRAM es global, muestreada cada1s, incluye escritorio/otros procesos; no es asignación aislada por modelo. Márgenes mínimos observados en V2:989MiB para8B y1840MiB para9B, sin garantía de mayor resolución/contexto/concurrencia. No se atribuye throughput a todo RTX3060 ni se extrapola a generación. Load timings, token usage y server_timings quedan en los JSON.

## Auditoría de explicaciones y límites

9B detectó texto prohibido, ambas llaves duplicadas/fusionadas y tres agujas de Z-Image. Su transcripción del texto como JAEGER-LECOULTRE no coincide con LONGINER observado/OCR previo: verdict correcto en ese caso, **evidencia textual alucinada**. Conservar el OCR especializado como señal independiente; no aceptar transcripciones del VLM por confianza.

9B declaró que había dos agujas en el caso MPT de tres, diciendo que la segunda aguja no se contaba “por contrato”. La cifra esperada en el prompt puede sesgar la observación; esto motivó V3. Ambos aceptaron geometría factual dañada y describieron relaciones gruesas (posición/objeto reconocible), sin establecer invariantes estructurales. Una puntuación1.0 de identidad/progresión es una declaración del modelo, no una medida calibrada.

El frío9B se rechazó por vapor visible; la inspección posterior muestra trazas ambiguas dentro/sobre el borde. Sigue sin adjudicación independiente; no se cambia expected uncertain. No se afirma que un tono azul o iluminación distinta prueben enfriamiento.8B no pudo completar los tres requests temporales en60s. Los timeouts no se convirtieron en pass.

La inspección directa confirmó tres agujas en el negativo MPT, las dos piezas/llaves fusionadas y dos agujas en la edición válida de tejido. Es revisión del agente, no validación ciega externa.3/16 decisiones y13 abstenciones del Florence rápido anterior no se equiparan a precisión perfecta: ese sistema evitaba aceptación por incertidumbre.9B aporta cobertura pero también dos aceptaciones peligrosas. Esta comparación no justifica sustituir el fail-closed por un pass confiado del VLM.

## Diagnóstico V3 y cierre

V3 estaba previsto para cinco casos por modelo, pero ambos alcanzaron60s en los dos primeros (texto prohibido/edición válida) y el corte evitó más llamadas. Resultado:4 solicitudes, todas unavailable. No se obtuvo un conteo ciego/crop válido y no se afirma que los recortes mejoren o empeoren precisión.

V4 control: solo9B, edición válida y reloj de tres agujas, mismas imágenes/ROI/cifras ocultas, retirando maxLength del schema. Dos solicitudes también timeout60s. [Registro](validation/visual-judge-schema-control-2026-10-08.json). El control no resolvió el bloqueo; **no se demuestra que grammar maxLength sea la causa**. Los snapshots/logs observados permanecían en prefill sin tokens finales. Hay que separar procesamiento visual, formas de ROI y backend en una prueba posterior; no subir timeout ni atribuir unavailable a defecto de imagen.

Total de esta fase:42 solicitudes VLM intentadas (4 V1,32 V2 únicos,4 V3,2 V4),0 solicitudes de generación de imágenes. Los cambios de protocolo son diagnósticos explícitos y se conservan separados; no son reintentos automáticos para rescatar una imagen. Se preservan todos los fallos. El dato decisorio sigue siendo la matriz V2 de16 casos por candidato.

## Validación y siguiente tarea

Tests finales del evaluador + QA existente:55 passed, exit0,3,33s. [Log](validation/visual-judge-harness-final-tests-2026-10-08.txt). Incluye16 casos del harness y39 QA, sin GPU/red en tests. No se cambió código productivo, dependencias globales, encoder, workflow, planner o flags persistidos; no corresponde atribuir el histórico387tests a este nuevo harness. Se ejecutaron hashes, JSON, diff y revisión de secretos antes del checkpoint.

La elección9B es para la **siguiente fase experimental**, no una promoción a ready. Siguiente tarea concreta: diagnosticar el prefill de ROI con controles de una sola imagen/texto y una versión de backend contrastada, hasta obtener una observación de cardinalidad ciega sin timeout. Después preparar el judge9B opt-in como evidencia adicional, conservar OCR/checks baratos independientes y exigir invariantes por componente para referencias factuales. El recorte no está aún validado para integración. Antes de habilitar admisión, resolver los dos FN y probar controles positivos/negativos adicionales con labels independientes. No generar más imágenes para ocultar errores del judge; reutilizar primero los artifacts.

No descargar otro candidato ni activar routing a raíz de este informe. Los procesos8092 deben quedar cerrados; al finalizar se puede volver a abrir el launcher8080 original. El sistema necesitará turnos de memoria para generación/QA/texto; no mantener los tres modelos residentes en12GB. Identificar SHA del informe final mediante Git y confirmar local/remoto/status en la respuesta de cierre.
