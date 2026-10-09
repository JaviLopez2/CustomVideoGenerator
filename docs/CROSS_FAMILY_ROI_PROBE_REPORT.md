# Contraste ROI con tazas conservadas — 2026-10-09

Desde `3907cd8d6aa884167e7aefaac0fd00deec179370`, mismo worktree/rama experimental, inicio limpio y diez worktrees comprobados. Se amplía únicamente el runner experimental y su preflight; el observador, prompt, schema y decoding existentes se conservan. Los SHA del código realmente ejecutado figuran en plan y raw, distintos del HEAD base aún sin el cambio. La aplicación MPT, modelos, routing y gates no se modifican.

## Procedencia y preflight

El protocolo v1 de A/B/C humano sigue separado y compatible. V2 distingue `byte_identity_control` —expectativa `not_observed` por bytes idénticos— de `unlabelled_pair` —expectativa null, sin gold humano—; rechaza campos de revisión humana/labels heredados y cualquier elevación de estas expectativas a gold perceptual. Labels, ids de casos, coordenadas y expectativas permanecen fuera del payload.

`scripts/paired_shape_preflight.py` liga por SHA diseño, resultado de preparación, plan, manifiesto y helper. Reconstruye en memoria las ocho regiones con el helper fijado, verifica flags/cajas/modo/píxeles y coteja el PNG conservado. No basta con confiar en un hash de crop o flag de cobertura reescrito. El runner hace el preflight antes de comprobar puertos/GPU/iniciar PID y lo repite antes de cada HTTP de modelo. `http_model_requests_attempted` cuenta el envío HTTP, separado del intento de invocar el callback local; un fallo local puede tener un row de intento y cero HTTP.

Solo los rectángulos `contained` son elegibles para este diagnóstico; parcial y fondo quedan excluidos, cero consultas. Esto protege frente a entradas incompletas conocidas, sin certificar cobertura semántica automática: cajas del asistente, revisión humana pendiente, `admission_allowed=false` y `physical_identity_established=false`.

TDD: 26 RED iniciales, luego 109 y 114 GREEN; dos regresiones detectan que cambiar las referencias a archivos alternativos internamente válidos eludía el diseño fijado. RED2 conservado y cotejo explícito diseño→resultado→plan/manifiesto corregido. Tests de claims/píxeles llaman también al verificador interno para comprobar la reconstrucción más allá de la protección por bindings. **116 tests finales pasan en 2,00 s, exit 0, sin avisos**, 33 nuevos y 83 anteriores. [Log final](validation/paired-shape-provenance-pinned-final-tests-2026-10-09.txt). Incluye source cambiado al cargar/entre casos, crop cambiado entre casos, conteo HTTP real, cierre de contexto propio, nulidad de gold y aislamiento de payload; sockets, Popen y HTTP de esas pruebas son simulados. La revisión independiente final no encuentra hallazgos. Código sin cambio posterior al run final.

## Cohorte real y resultados

[Diseño previo](validation/cross-family-roi-probe-design-2026-10-09.json) y [plan ejecutable fijado](validation/cross-family-roi-probe-plan-2026-10-09.json). Tres pares por cada uno de los dos jueces ya instalados, secuenciales: roja/roja, azul/azul y roja/azul; todos con los mismos recortes anteriores +8 px. Dos controles duplicados y un par de recolor no son tres ejemplos independientes ni negativos estructurales. No se reabren las microediciones de taza fallidas ni se generan otras imágenes.

| Caso | Tipo de evidencia | Qwen3.5 | Qwen3-VL |
|---|---|---|---|
| Roja consigo misma | Bytes idénticos; control de consistencia | not_observed | not_observed |
| Azul consigo misma | Bytes idénticos; control de consistencia | not_observed | not_observed |
| Roja/azul conservadas | Sin gold humano de forma; no correctness score | not_observed | not_observed |

Los dos modelos establecen presencia en ambos inputs. Cuatro respuestas concuerdan con los controles de identidad de bytes; las otras dos son observaciones cualitativas sin precisión/TP/TN/FP/FN asignados. El texto raw que dice «identical» no certifica igualdad geométrica ni identidad física. Los seis diagnósticos finales siguen `uncertain`, sin admisión/rechazo automático. Esta segunda familia muestra consistencia limitada; **no demuestra sensibilidad a defectos, calibración, ranking poblacional o promoción**. [Raw Qwen3.5](validation/cross-family-roi-qwen35-2026-10-09.json), [raw Qwen3-VL](validation/cross-family-roi-qwen3vl-2026-10-09.json), [análisis](validation/cross-family-roi-analysis-2026-10-09.json).

| Modelo | n solicitudes | Media, s | Mediana, s | Carga propia, s |
|---|---:|---:|---:|---:|
| Qwen3.5-9B Q4_K_M | 3 | 4,703 | 4,746 | 4,068 |
| Qwen3-VL-8B Instruct Q4_K_M | 3 | 4,168 | 4,575 | 4,036 |

Tiempos locales incluyen preparación del payload, recheck de regiones, HTTP y parseo. Carga separada; no se mide todo MPT/QA, tiempo total de hash de pesos/proceso ni p95 representativo. Qwen3-VL reutiliza prefijo: 153 tokens en azul/azul y 1209 en roja/azul; Qwen3.5 reporta cero. No declarar ganador de velocidad general por estas tres consultas. El preflight registró 22% de utilización GPU, no GPU perfectamente idle ni medición de pico de VRAM.

## Recursos y cierre

[Preflight](validation/cross-family-roi-resource-preflight-2026-10-09.json): RAM libre 17,58 GiB, VRAM usada 1106 de12288 MiB, 8080/8092 libres, bridge8090 HTTP404 —respuesta, no readiness—, Comfy8188 HTTP200 y cola0/0. Archivos existentes de ambos modelos y proyectores rehasheados; dos ZIP oficiales y 54 DLL/EXE verificados por cada inicio. No resolución/descarga de assets nuevos.

**Seis consultas reales completadas, stop/0 reasoning, cero retries/generaciones/descargas.** Dos PID propios cerrados y comprobados ausentes antes de continuar; 8092 libre. Entre cohortes se verificó cola0/0. Servicios compartidos conservados; no supervisor Factory/jobs/benchmarks GPU globales/deps/app/defaults/workflows/routing/gates/estable cambiados. [Cierre](validation/cross-family-roi-closing-checks-2026-10-09.json). Conservar logs ignorados bajo `target/cross-family-roi-qwen35-2026-10-09` y `target/cross-family-roi-qwen3vl-2026-10-09`, junto a fuentes y recortes anteriores. Raw JSON UTF8 intacto; un render de consola Windows sustituyó guiones tipográficos, no el artifact.

## Próximo paso autónomo

Cerrar esta cohorte sin más recolors/self-pairs o ajuste de prompt/crops para mejorar respuestas. La sensibilidad geométrica sigue pendiente de negativos válidos y revisión independiente; no promover desde los tres pares de llave ni desde duplicados de taza. Siguiente tarea: auditar por inspección los tres estados temporales conservados y sus contratos, fijar un protocolo de evidencia visual directa que distinga identidad, pistas de estado y progresión; no atribuir temperatura por color/luz ni convertir ausencia de caption en fail. Preparación CPU primero, con los labels/captions históricos intactos y gold humano ausente explícito; luego solo las consultas con información que justifique la prueba. Mantener fail-closed experimental. No requiere abrir8080 ni nueva aprobación rutinaria.
