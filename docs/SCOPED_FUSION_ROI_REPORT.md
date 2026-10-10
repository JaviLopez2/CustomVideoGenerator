# Contraste de estructura con ROI nativo — 2026-10-11

Cuatro consultas nuevas sobre el par retenido de llave 1→3 aportan señales parciales, sin una descripción explícita de los dos tallos convergiendo bajo un cabezal. Qwen3.5 pasa de `not_observed` en fullframe a `observed` en ROI; Qwen3-VL conserva `uncertain`. Ambos controles idénticos son `not_observed`. Ningún juez queda aprobado para geometría o identidad y los fallos fullframe permanecen en su cohorte cerrada.

## Procedencia y alcance

Base de ejecución: `3579f6531cddbb7163bbc7e932a773d0440c5c41`, rama experimental `factory/image-model-routing-modernization`. [Plan fijado](validation/scoped-fusion-roi-plan-2026-10-11.json), [recipe](validation/scoped-fusion-roi-recipe-2026-10-11.py), [preparación](validation/scoped-fusion-roi-preparation-2026-10-11.json). Las consultas empezaron después de fijar inputs, orden, prompt, schema y presupuesto; sus timestamps UTC corresponden a la noche del 10 y a la fecha local del 11 de octubre.

El origen nativo de referencia es `029f4b8d36a062f932c0fbcea2394856f8dd079773bc051384869c1f4b0d9352`; el candidato fusionado es `e9f2b705e0d71798b2dbc3cde7f5053a99a1f6ee3122eeaa1141a72f7fbdb925`. El B de A/B/C, `224e68ed…`, es otra imagen: no se duplica ni se transfiere su etiqueta. La [revisión humana de relojes](validation/clock-visible-count-human-review-2026-10-10.json) señala dos formas de llave convergentes en 3; no certifica dos objetos separados. La preferencia estética por 4 sigue separada de la identidad.

Se recortan los fullframes RGB8 previamente preparados, sin nueva generación ni resampling. Caja manual idéntica `[430,530,720,970]`, margen uniforme de 8 px, caja efectiva `[422,522,728,978]`, dos PNG de 306×456. La reconstrucción verifica exactamente los subconjuntos de píxeles nativos, sin resize, overlays o cambio de color. El asistente inspeccionó fullframes y crops: cabezal compartido, ambos tallos y extremos de dientes parecen completos. Esa inspección no es adjudicación humana independiente del crop; el rectángulo por sí solo tampoco acredita cobertura física. Un fragmento del reloj permanece a la izquierda.

Se conservan sujeto, estructura protegida, estados permitidos vacíos, prompt, schema y decoding del [contraste fullframe](SCOPED_STRUCTURE_PROBE_REPORT.md). No se envían al juez cajas, números esperados, etiquetas humanas o una descripción de la fusión. La selección sigue al fallo anterior y es exploratoria, no holdout. Contexto y resolución efectiva cambian juntos: no se atribuye causalmente el resultado a atención, resolución o recorte por separado.

## Resultado literal e interpretación

| Par | Qwen3.5: estructura / conexiones | Qwen3-VL: estructura / conexiones |
|---|---|---|
| Crop idéntico | not_observed / not_observed | not_observed / not_observed |
| Referencia → candidato fusionado | observed / observed | uncertain / uncertain |

Qwen3.5 describe dos llaves, un cabezal circular y una adición/deformación de partes. Afirma además que una llave coincide con la referencia, sin que quede acreditada esa identidad. No describe la unión de dos tallos en un cabezal común. Qwen3-VL menciona una segunda llave, diferencias de aro/tallo/diente y oclusión; se abstiene de verificar la estructura. Tampoco describe la unión humana. No se concede detección correcta de fusión por el enum `observed`, por mencionar una segunda llave o por abstenerse.

[Raw Qwen3.5](validation/scoped-fusion-roi-qwen35-2026-10-11.json), [raw Qwen3-VL](validation/scoped-fusion-roi-qwen3vl-2026-10-11.json), [análisis ligado por SHA](validation/scoped-fusion-roi-analysis-2026-10-11.json). Cuatro respuestas `stop`, cero reasoning y cero retries, generaciones o descargas. Dos solicitudes por juez, máximo 512 tokens, temperatura 0, contexto 8192 e imagen 1024–1536 tokens. Se verificaron los pesos/projectors existentes y runtime b11497, ambos ZIP y 54 archivos extraídos; no se cambia el modelo configurado en MPT.

Todos los diagnósticos permanecen `uncertain`, sin admisión, rechazo automático, identidad física o verdad de píxeles establecida por el modelo. Esto no demuestra precisión poblacional ni selección de juez estructural.

La preparación de payload ocupa 0,0158–0,0170 s por par. El intervalo de preflight transitivo + HTTP + parsing es 7,394/8,030 s en Q35 y 8,391/7,216 s en VL; carga de cada servidor propio: 4,041/4,042 s. Cached prompt tokens: Q35 0/0, VL 0/1363. No son tiempos de QA completo de MPT, comparación causal de velocidad, p95 ni medición de pico VRAM.

## Validación y cierre

**[147 tests pertinentes pasan, 2,04 s, exit 0](validation/scoped-fusion-roi-tests-2026-10-11.txt)**. Son tests existentes ejecutados de nuevo sobre el observador, preflight/runner pareados y preparación nativa; no se atribuyen tests nuevos o mediciones antiguas a este cambio. Comando desde este worktree, `MPT_RUN_INTEGRATION_TESTS=0`:

```powershell
& 'D:/Apps/MoneyPrinterTurbo-Portable-Windows-1.3.6/lib/python/python.exe' -B -m pytest -q test/test_scoped_structure_observations.py test/test_paired_shape_observations.py test/test_paired_shape_preflight.py test/test_paired_shape_runner.py test/test_prepare_visual_regions.py --tb=short
```

[Siete controles CPU](validation/scoped-fusion-roi-cpu-controls-2026-10-11.json) rechazan alteraciones de presupuesto, cajas, scope, roles, request, source y candidatos; plan original conservado. Revisión independiente de la receta: sin hallazgos; verify-only reconstituye dos pares con cero consultas. Se revalidan bindings, raw choices, roles, estado de parsing y presupuesto después de ambas cohortes.

[Recursos al cierre](validation/scoped-fusion-roi-resource-closing-2026-10-11.json): PID propios 8728/18620 ausentes, `OpenProcess` error 87; 8092 libre. RAM libre 17,68 GiB, GPU 1151/12288 MiB y 7% de utilización, sin pico medido. 8080 cerrado, bridge 8090 HTTP 404 solo liveness, ComfyUI 8188 HTTP 200. Ningún control de servicios compartidos, cambio de app/QA/defaults/routing/deps/workflows/estable o nuevo peso. [Checks finales](validation/scoped-fusion-roi-closing-checks-2026-10-11.json); SHA de entrega mediante Git/origin.

## Continuación autónoma

Preparar en CPU controles procedurales de conexiones fuera de la familia de llaves, con positivos, negativos y estados permitidos cuya procedencia y etiquetas se expliquen por construcción. Mantenerlos separados del gold humano de imágenes reales: no pueden aprobar identidad ni sustituir la calibración independiente. Fijar inputs y presupuesto antes de cualquier nueva inferencia; no retocar ni repetir esta cohorte para rescatarla.

La revisión estructural humana de cámara sigue pendiente; no se repite la de relojes. Calibración independiente, errores/abstención, otra familia de defectos humanos y latencia de QA completo siguen pendientes. El objetivo continúa activo y la preparación CPU no necesita abrir servidores ni otra aprobación rutinaria.
