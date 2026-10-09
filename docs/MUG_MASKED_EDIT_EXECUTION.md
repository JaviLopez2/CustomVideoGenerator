# Edición enmascarada de taza — ejecución, 2026-10-09

Una edición completó técnicamente y conservó exactamente los píxeles fuera de máscara, pero **no creó un negativo estructural limpio**. La inspección del asistente en detalle4× ve la unión inferior aún conectada y un borde de parche. La cohorte se cierra inutilizable para evaluar sensibilidad de los jueces. No se pide al usuario certificar un resultado ya descartado por estos criterios.

Base `f36b2a148b0725d387bb6c54e9eadef3ad5da4fa`, misma carpeta/rama experimental, status/diffs iniciales vacíos y diez worktrees. Usuario abrió servicios excepto8080 y autorizó continuidad autónoma. [Preparación previa](MUG_MASKED_EDIT_PREPARATION.md) y su grafo permanecen intactos. [Preflight fresco](validation/mug-masked-generation-preflight-2026-10-09.json), [input](validation/mug-masked-input-2026-10-09.json), [ejecución](validation/mug-masked-generation-2026-10-09.json), [inspección independiente del resultado técnico](validation/mug-masked-assistant-review-2026-10-09.json), [cierre](validation/mug-masked-generation-closing-checks-2026-10-09.json).

## Evidencia observada

- Una solicitud directa al Comfy compartido8188, HTTP200; prompt_id `dadeec50-4ca4-4b0b-999b-06bd39b626b0`, success/completed. 512×512,4 pasos,seed42,guidance1; cero retries y cero consultas a jueces. Tiempo total desde el POST hasta lectura de PNG: **12,328s**, no benchmark controlado ni medición aislada de sampling.
- Resultado SHA `ae2ea098dccfc6068d414ad0730cc1e5b0f210989c6c32cd239eafe0a4070bdf`. Se verifican **0 píxeles diferentes fuera de máscara y1213 dentro**. Diferencias exactas RGB, no score perceptual, identidad física o certificado del corte.
- Original rojo y máscara se revalidan por SHA. Máscara copiada al nombre único fijado mediante permiso específico, sin sobrescribir otro input. Tres pesos rehashados, bindings y plantillas iguales; 20 nodos/26 enlaces compatibles con contratos vivos. La ejecución acredita esta ruta de tensors/modelo para el caso, no calidad general de inpainting ni VRAM máxima.
- Recursos globales antes: RAM libre19,34GiB, VRAM libre10,99GiB; cola vacía antes/después. Son snapshots, no picos por modelo. 8080 no responde;8090 devuelve404 y8188 responde200. Servicio compartido conservado; ninguno iniciado, detenido o reconfigurado por el agente.
- [Tablero](D:/Apps/MPT-worktrees/image-model-routing-modernization/local_image_stack/experiments/bridge/target/mug-masked-generation-2026-10-09/review-board.png) conserva originales completos y detalle directo4×; PNG original/resultado incrustados por sus bytes. SVG/PNG, request, response e historial de este job se guardan en target ignorado y deben conservarse al archivar.

## Interpretación y siguiente hipótesis

El contrato de composición funciona: limita cambios al interior de la región revisada. El éxito técnico no garantiza un defecto utilizable. No se conoce aún la causa interna del parche; la referencia visual y la región latente pequeña son hipótesis, no causas demostradas. Las uniones positivas tampoco quedan aprobadas por la anterior revisión de región.

La siguiente cohorte retira solo el conditioning ReferenceLatent, conserva latente de imagen/máscara, prompt y parámetros, y guarda también el decode previo a composición. [Plan fijado antes de ejecutar](validation/mug-masked-no-reference-plan-2026-10-09.json). Presupuesto propio: una solicitud, cero retries. Es una ablación declarada, no un reintento automático ni reapertura de esta cohorte. Si falla, cerrar la hipótesis antes de considerar otra metodología; no inferir fallo de un juez ni promocionar modelos.

Sin cambios de código productivo, modelos, deps, routing, gates o workflows activos. Los112 tests de preparación son históricos del código sin cambios; esta fase valida HTTP/historial, SHA, conservación y revisión visual, sin atribuir un nuevo pytest. SHA del checkpoint de cierre mediante Git/origin, distinto de execution_base. La [autorización y continuidad](AUTONOMOUS_MPT_WORK_HANDOFF.md) permiten seguir después del checkpoint sin esperar otro «sigue».
