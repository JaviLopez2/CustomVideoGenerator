# Recuentos ciegos y fusión visible — 2026-10-10

Qwen3.5 coincide con los ocho recuentos humanos de agujas/llaves; Qwen3-VL coincide con cinco. **Ninguno describe la fusión de dos tallos en un cabezal de la imagen 3.** Es un conjunto diagnóstico de cuatro imágenes seleccionadas, no una medición general de precisión. Ningún juez queda aprobado ni se cambian las decisiones de MPT.

Base `1833e8b2d9bf2d4d8903338cd9ef4a5e3183436e`, experimental inicialmente limpio/diez worktrees. [Plan](CLOCK_BLIND_AND_FUSION_PROBE_PLAN.md), [raw Qwen3-VL](validation/clock-blind-fusion-qwen3vl-2026-10-10.json), [raw pareado Qwen3.5](validation/clock-fusion-qwen35-2026-10-10.json), [análisis](validation/clock-blind-fusion-analysis-2026-10-10.json). Se completaron exactamente seis consultas nuevas: cuatro full QA ciego a Qwen3-VL y un nuevo par 1→3 por modelo; todas terminaron con `stop` y sin reasoning, cero retries/generaciones/descargas. Se reutilizaron las cuatro respuestas full QA archivadas de Qwen3.5, sin repetirlas. Las cohortes quedan cerradas, sin ajustar posteriormente el método para mejorar sus resultados.

| Imagen | Humano agujas/llaves | Qwen3.5 archivado | Qwen3-VL nuevo |
|---|---|---|---|
| 1 | 2/1 | 2/1 | 2/1 |
| 2 | 3/1 | 3/1 | 2/1 |
| 3 | 2/2, convergencia en un cabezal | 2/2 | 2/1 |
| 4 | 3/1 | 3/1 | 2/1 |

Se comparan solo las ocho cantidades expresadas por el usuario; el contrato tiene otros cuatro campos de número de relojes que no se convierten en nuevas valoraciones humanas. Ningún modelo se abstiene en esas ocho cantidades. La revisión estética de la imagen 4 permanece separada de identidad; la geometría de las otras tres imágenes no está adjudicada. No se modifica la valoración A/B/C ni los antiguos labels de asistente/contrato.

En el full QA de la imagen 3 ambos dicen `geometry=pass`. Qwen3-VL acepta globalmente la imagen porque su recuento de una llave coincide con el contrato de una, pese al recuento humano de dos y a la fusión. El fail global archivado de Qwen3.5 procedía de cantidad dos contra una; no demuestra que detectase la geometría defectuosa.

En el **nuevo contraste pareado genérico**, ambos reportan `major_shape_change=observed`, pero sus evidencias no describen dos tallos unidos por un cabezal. Qwen3-VL habla del cabezal circular añadido. Qwen3.5 describe dos llaves, una supuestamente idéntica a la referencia y otra añadida con cabezal grande: esa identidad no está verificada y la descripción no recoge la unión señalada por el usuario. Son hints de cambio de partes, no una demostración de sensibilidad a fusión. Ambos diagnósticos siguen `uncertain`, sin admisión o identidad física. No usar una categoría `observed` para certificar una evidencia específica ausente.

El constructor de full QA, prompts/schema/runtime/assets y roles/hashes coinciden con los históricos, y las cantidades esperadas y la revisión humana quedan offline. La comparación se basa en requests reconstruidos con código sin cambios y fuentes fijadas; no hay una captura histórica del tráfico HTTP. La selección de cuatro casos fue posterior a resultados antiguos; secuencia/cache/carga diferentes impiden inferir precisión general o una comparación causal de rapidez.

Las cuatro duraciones locales de Qwen3-VL fueron 8,926/4,858/10,148/4,851 s; el par Qwen3-VL tardó 4,904 s y Qwen3.5 tardó 5,394 s. Carga propia de 4,051/4,037 s respectivamente. El timer de la receta incluye revalidación antes del HTTP y persistencia; no mide solo latencia de transporte ni QA completo de MPT. No se midió pico de VRAM en esta fase. Conservar los timings/cache originales en raw.

[Verificación de preparación](validation/clock-blind-fusion-preflight-controls-2026-10-10.json): diez controles rechazados, blinding/roles/fingerprints comprobados y 67 tests relevantes pasan en 1,21 s, exit 0. Una revisión independiente de código y procedencia no encontró problemas; no ejecutó inferencias ni cambió archivos. [Cierre](validation/clock-blind-fusion-closing-checks-2026-10-10.json): código/fuentes revalidados tras las consultas, PID propios 13224/11408 ausentes mediante `OpenProcess`, error 87; 8092 libre, RAM 17,94 GiB libre, VRAM 1174/12288 MiB, GPU 4%. 8080 cerrado, 8090 HTTP 404 solo liveness y 8188 HTTP 200. MPT estable conserva 6d27ba4, rama protegida y árbol tracked limpio. No se controlaron servicios compartidos ni se modificaron app/defaults/gates/routing/modelos/deps/workflows/producción.

Próximo: preflight de cámara que ligue la preparación explícita de color/alpha con fuentes y cobertura, y controles independientes de partes/uniones en otra familia. Qwen3.5 sigue como candidato preferente **para cantidades en este conjunto**; falta calibración estructural/abstención/error entre familias y latencia QA completa antes de seleccionar o promover un juez. Objetivo activo, sin pedir otra aprobación rutinaria ni repetir la revisión de relojes. SHA de entrega posterior mediante Git/origin.
