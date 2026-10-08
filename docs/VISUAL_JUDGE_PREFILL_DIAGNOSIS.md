# Diagnóstico de prefill y conteo ciego — 2026-10-08

Los seis controles preparados completaron con la GPU en reposo. El timeout previo de texto ocurrió mientras el usuario jugaba y no demuestra un fallo intrínseco de Qwen3.5. El conteo ciego sobre imagen completa detecta las tres agujas del negativo MPT que se aceptó en V2; un recorte aislado inventa una tercera aguja en el positivo. No se habilita admisión ni routing.

Base de ejecución `9f4296485698bf98539eb284cdec509721a865ee`, rama experimental `factory/image-model-routing-modernization`. Sin cambios de código en esta ejecución. Mismos pesos Qwen3.5-9B Q4_K_M/projector F16 fijados y verificados, runtime portátil b11497/ff30363a0. Cero descargas, generaciones, cambios de dependencias, workflows o producción. El SHA del checkpoint documental se obtiene del historial.

## Dos ejecuciones conservadas

1. Tras cierre de8080: baseline3108MiB globales, carga18.530s, control de texto timeout60.010s; se cancelaron los cinco controles visuales previstos. El servidor propio quedó cerrado. La GPU seguía al86–100% con87–89°C tras su cierre. El usuario confirmó un juego abierto usando continuamente la GPU. [Resultado original](validation/visual-judge-prefill-controls-2026-10-08.json), [interpretación/provenance](validation/visual-judge-prefill-resource-diagnosis-2026-10-08.json). No se reescribió el resultado bruto ni se imputó ese timeout a la gramática o al modelo. Una consulta inicial de contadores mezcló Running Time y Utilization Percentage: sus cifras no se usan como porcentajes; la consulta corregida tuvo una muestra inválida y solo ofrece corroboración parcial.
2. El usuario cerró el juego y mantuvo8080 cerrado. Antes de inferencia, dos lecturas separadas3s:1000MiB globales,3% GPU,42–43°C,~22W; Comfy queue0/0. Se ejecutó el plan completo con nombres nuevos. [Resultado en reposo](validation/visual-judge-prefill-idle-controls-2026-10-08.json). Todos los procesos propios cerrados; las verificaciones finales quedan en [closing checks](validation/visual-judge-prefill-closing-checks-2026-10-08.json).

Total de esta continuación:7 requests al modelo (1 afectada por el juego +6 en reposo), de ellas5 visuales; cero generaciones de imágenes. La repetición del control de texto fue un diagnóstico explícito tras eliminar una carga externa confirmada, sin retries automáticos ni sobrescritura. La fase histórica de42 solicitudes se conserva por separado.

## Protocolo y resultados en reposo

Cada control usa un servidor8092 nuevo, context8192, una slot, GPU layers99 solicitadas, Flash Attention on, razonamiento off, min1024/max1536 tokens por imagen, temperatura0, schema counts-only sin maxLength, máximo192 tokens finales y timeout60s. Se omiten referencias, requisitos geométricos/textuales y cantidad esperada. Se pregunta por todas las agujas visibles, incluida la de segundos. Imagen completa y recorte son vistas del MISMO objeto. Recortes analíticos preexistentes, hashes verificados. No es el protocolo V2 completo ni una ablación de un único factor frente a V3/V4.

| Control | Conteo observado | Tiempo HTTP | Interpretación |
|---|---:|---:|---|
| Texto sin imagen | null, uncertain | 1.199s | Transporte/schema funciona |
| Positivo completo | 2 | 3.864s | Correcto |
| Positivo recortado | 3 | 3.733s | Falso defecto; tercera aguja inventada |
| Positivo completo + recorte | 2 | 4.954s | Correcto |
| Negativo completo | 3 | 3.790s | Detecta el defecto previamente omitido |
| Negativo recortado | 3 | 3.725s | Correcto |

Carga de cada servidor3.516–3.521s, informada aparte. Finish reason stop y cero reasoning en los seis controles. La inspección directa de los dos recortes confirma dos/tres agujas respectivamente; sigue siendo revisión del agente, no adjudicación humana independiente. La explicación del positivo recortado asegura una aguja de segundos cerca de1:30 que no se ve. Las cinco filas visuales son vistas de SOLO DOS imágenes: no son cinco casos independientes ni prueba estadística de fiabilidad.

La VRAM del JSON es baseline/post-request global, no pico monitorizado ni asignación del modelo; no atribuirle los picos V2. Los tiempos cortos corresponden a una pregunta enfocada sin referencias; no reemplazan los27.786s de media del contrato completo V2. El aislamiento GPU y el protocolo cambiaron; no se demuestra cuánto aporta cada factor a la mejora.

## Qué queda establecido y qué falta

El runtime/modelo/schema pueden responder sin timeout con GPU libre, tanto a texto como a las formas de recorte probadas. No se reprodujo el bloqueo en estos controles; la carga del juego explica la confusión de la primera ejecución, pero no prueba retrospectivamente la causa de todos los timeouts V3/V4. Los avisos históricos de posiciones de tokens tras cancelar tampoco establecen causalidad.

No descargar otra versión de backend por este resultado. Como contexto histórico, upstream documentó un fallback CPU del projector con FA en otros builds/configuraciones ([issue21272](https://github.com/ggml-org/llama.cpp/issues/21272), Linux/RTX5060Ti, cerrado y bug-unconfirmed) y fusionó una corrección de barrera f16 FA el7 de septiembre ([PR27870](https://github.com/ggml-org/llama.cpp/pull/27870), otras GPU/CUDA). Ninguna demuestra que este Windows/RTX3060/b11497 tenga esos fallos; son pistas para un eventual contraste si reaparece el problema en reposo.

Siguiente tarea concreta: evaluar el conteo ciego dentro del contrato completo con imagen completa como señal principal, y auditar geometría de la llave deformada contra su referencia junto al control positivo Qwen. Mantener los resultados/labels previos, OCR independiente y fail-closed. Un recorte aislado no debe decidir admisión. La llave deformada, identidad y progresión siguen sin resolver; no integrar automáticamente a raíz de seis controles.

Validación: hashes de pesos/inputs antes de inferencia, JSON y respuestas/checks revisados, diff y patrones de secretos comprobados al cierre. Los58 tests offline del código de preparación pertenecen al checkpoint9f42964 (log existente); no se presentan como una nueva ejecución de pytest. Aquí solo cambian documentación/evidencias, no código productivo ni tests. Estable protegido debe conservar6d27ba4963ffe469d635db71eaeec506a8ff4b61 y tracked tree intacto. Se puede volver a abrir8080 y el juego tras cerrar el diagnóstico; futuras pruebas GPU necesitan reservar recursos de nuevo.
