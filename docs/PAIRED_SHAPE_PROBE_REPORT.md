# Comparación visual conjunta de forma — 2026-10-09

Los dos jueces fallan el cambio importante de B con el fotograma completo y lo detectan al concentrar la entrada en la llave. A/C permanecen sin cambio importante en ambas modalidades. Es evidencia prometedora sobre tres pares conocidos; todavía no valida un gate de geometría, un localizador automático o identidad física.

## Protocolo y procedencia

Implementación desde `0746505930e23ddbb007c6eda0634fde9f821037`, publicada en `92ea66495ff39dfc9368791a0802e6b54b183c49`, también HEAD de las cuatro cohortes. `scripts/paired_shape_observations.py` y `scripts/observe_paired_shape.py` son herramientas experimentales aisladas; no cambian el caller, los gates o el routing de MPT. Parser estricto: cuatro campos, presencia compatible, JSON sin claves duplicadas, final no vacío, `finish_reason=stop`, reasoning vacío. Un error cierra esa cohorte sin retry y conserva lo recibido. Cada diagnóstico conserva `uncertain`, sin admisión, veto automático o identidad.

La revisión humana [A/B/C](validation/visual-geometry-human-review-2026-10-08.json) se conserva literalmente y solo interviene en el análisis posterior. A: forma conservada con anillos algo mayores; B: forma completamente cambiada; C: sin cambio visible. No se convierte A en identidad exacta ni se inventan counts/tolerancias. Los seis PNG originales están fijados por SHA, cuatro únicos, 768×1376. La máscara disputada de B no se usa.

Dos modelos ya instalados: `unsloth/Qwen3.5-9B-GGUF` y `Qwen/Qwen3-VL-8B-Instruct-GGUF`, Q4_K_M con sus proyectores F16. Runtime b11497: dos ZIP oficiales y 54 DLL/EXE extraídos comprobados por hash; el runner revalida runtime/pesos antes de cada cohorte. Puerto propio8092, oculto, slot1, context8192, image tokens1024–1536, temperature0, max256, thinking=false, schema común, timeout60s. Primero Qwen3.5 y después Qwen3-VL, sin concurrencia. Imagen1 referencia, imagen2 candidato; sin nombres de pares, labels, anotaciones ni coordenadas en el payload.

[Plan completo](validation/paired-shape-probe-plan-2026-10-09.json) y [preflight de implementación](validation/paired-shape-execution-preflight-2026-10-09.json). El prompt compara forma y disposición de partes principales, excluye color/luz/textura y no considera un tamaño local menor suficiente para un cambio importante. Este protocolo conjunto es distinto del QA general y de los inventarios previos; no es una ablación de un único factor respecto a aquellos.

## Fotograma completo: fallo conservado

| Caso | Cambio importante humano | Qwen3.5 | Segundos | Qwen3-VL | Segundos |
|---|---|---|---:|---|---:|
| A | No; variación menor de anillos | not_observed | 4,935 | not_observed | 5,100 |
| B | Sí | not_observed | 4,829 | not_observed | 3,981 |
| C | No | not_observed | 4,801 | not_observed | 5,041 |

Por modelo: TP0/TN2/FP0/FN1/uncertain0/unavailable0 **para la categoría observada**, sin convertir los diagnósticos en pass. Qwen3-VL describe diferencias en cabeza y cortes de B, pero su categoría sigue siendo `not_observed`: no se rescata la respuesta con esa prosa. [Raw Qwen3.5](validation/paired-shape-qwen35-2026-10-09.json), [raw Qwen3-VL](validation/paired-shape-qwen3vl-2026-10-09.json), [análisis](validation/paired-shape-analysis-2026-10-09.json).

## Contraste de entrada: recortes previamente delimitados

Tras cerrar esas dos cohortes se fija un [plan separado](validation/paired-shape-roi-probe-plan-2026-10-09.json), seis consultas/0 retries. Reutiliza regiones del [plan espacial anterior](validation/spatial-geometry-audit-plan-v2-2026-10-09.json), definido antes de estas respuestas, con margen uniforme de8px y sin ajustar cada caja según el resultado. Cada PNG recortado contiene exactamente el subconjunto original de píxeles y mantiene su modo RGB/RGBA; sin redimensionar, máscara, reconstrucción o transformación de color. Los cuatro recortes fueron inspeccionados por el asistente y A/B contrastados con sus fotogramas completos: las partes principales visibles permanecen dentro. Esto revisa la preparación, no añade gold humano. [Preflight](validation/paired-shape-roi-preflight-2026-10-09.json).

La primera preparación se detuvo por una aserción RGB innecesaria ante el PNG RGBA de A. No hubo inferencia: se conservó el primer recorte y se completó preservando el modo original, con verificación exacta de píxeles. La lectura Git de la copia estable requirió `safe.directory` únicamente en el comando de lectura, por la identidad de Windows del sandbox; sin cambiar configuración global/ACL.

Prompt, schema, criterios, decoding, modelos y orden A/B/C se conservan. Cambia únicamente la presentación de las entradas mediante recorte, que modifica **contexto y resolución visual efectiva a la vez**. No permite atribuir el efecto exclusivamente a resolución ni mejora el número de píxeles de la fuente. Los payloads son idénticos entre modelos en cada caso dentro de cada modalidad, comprobados por hash antes y después del envío.

| Caso | Cambio importante humano | Qwen3.5 ROI | Segundos | Qwen3-VL ROI | Segundos |
|---|---|---|---:|---|---:|
| A | No; variación menor de anillos | not_observed | 4,761 | not_observed | 4,812 |
| B | Sí | observed | 4,828 | observed | 3,297 |
| C | No | not_observed | 4,478 | not_observed | 4,825 |

Por modelo: TP1/TN2/FP0/FN0/uncertain0/unavailable0 en esta tarea concreta. Ambos mencionan cabeza con abertura y cambio de forma de B; no hay reinterpretación categórica. [Raw Qwen3.5 ROI](validation/paired-shape-roi-qwen35-2026-10-09.json), [raw Qwen3-VL ROI](validation/paired-shape-roi-qwen3vl-2026-10-09.json), [análisis del contraste](validation/paired-shape-roi-analysis-2026-10-09.json).

## Tiempos, recursos y pruebas

| Modelo / entrada | n | Media solicitud, s | Mediana, s | Carga propia, s |
|---|---:|---:|---:|---:|
| Qwen3.5 / completa | 3 | 4,855 | 4,829 | 4,040 |
| Qwen3-VL / completa | 3 | 4,707 | 5,041 | 4,041 |
| Qwen3.5 / ROI | 3 | 4,689 | 4,761 | 4,031 |
| Qwen3-VL / ROI | 3 | 4,311 | 4,812 | 4,033 |

Tiempos locales de la solicitud incluyendo preparación/HTTP/parseo; carga del servidor separada. No se mide QA completo ni benchmark poblacional/p95 con n3. Qwen3-VL reutiliza prefijo del servidor en B y parcialmente C (completa1187/153 tokens; ROI1211/153); Qwen3.5 reporta0 en estas solicitudes. El orden y cache influyen en latencia; no declarar ganador global ni ahorro end-to-end del pipeline con esta tabla.

Antes de ROI: GPU usada1105MiB, RAM libre17,84GiB,8080/8092 libres,8090HTTP404,8188HTTP200 y cola0/0. Es disponibilidad/preflight, **no pico de VRAM medido durante inferencia**. No se cambió ningún servicio compartido. Cuatro servidores propios cerrados; outputs/PID/estado de puerto registrados.

Prueba de implementación ejecutada en esta fase: **184 passed in7.34s, exit0,0 warnings,51 nuevos**, [log](validation/paired-shape-final-tests-2026-10-09.txt). 34 tests de observación/15 iniciales de runner/2 de propiedad del proceso, con RED y GREEN conservados. Se valida orden exacto de bytes, aislamiento de labels, salida inválida/truncada/reasoning, budgets, timeout, cambio de input, extracción de runtime y cierre del PID propio incluso ante readiness fallida. Las fuentes no cambiaron desde esa ejecución; no se atribuye este resultado a código posterior. Revisión independiente sin hallazgos. [Cierre verificable](validation/paired-shape-closing-checks-2026-10-09.json).

12 consultas nuevas, todas completadas/stop/0 reasoning;0 retries,0 generaciones/descargas/benchmarks,0 nuevas dependencias o pesos. Aplicación, modelos, plantillas activas, flags, gates, routing, Factory y copia estable protegida permanecen intactos. Conservar los directorios ignorados `paired-shape-*` con cuatro recortes y logs de los cuatro servidores, además de todos los originales. Los raw JSON ligeros quedan versionados.

## Siguiente paso

Prioridad inmediata: [auditoría CPU](validation/temporal-caption-ambiguity-audit-2026-10-09.json) confirma cuatro desacuerdos con el contrato temporal en `state_check`: mención cualificada se convierte en pass, contradicción presencia/ausencia en pass, ausencia anterior cualificada acredita progresión y presencia prohibida cualificada se convierte en fail. Corregir ese parser de forma genérica con TDD y bump de versión de caché, conservando fail negativo inequívoco. La caché y los checks selectivos ya existen; no repetirlos ni añadir otra capa sin evidencia de beneficio. Este siguiente parche todavía no forma parte del presente checkpoint.

Después, conservar el observador ROI como candidato diagnóstico y preparar de forma reproducible regiones ligadas a fuentes, con casos retenidos de otra familia y controles de ausencia/recorte incompleto. Declarar cohortes antes de consultar y separar labels humanos de inspección del asistente. Las cajas manuales no son un localizador automático; sin sensibilidad y cobertura probadas no añadir admisión, veto o routing. Los controles estructurales de taza anteriores siguen cerrados inutilizables y no se usan para medir sensibilidad. La continuidad autónoma sigue activa, sin nueva aprobación rutinaria.
