# Klein 4B: continuidad, resolución y detalles — 2026-10-07

Base experimental `6ba2402da916925e1334ba31e68b4fb6cf486cf8`. El usuario autorizó continuar con pruebas de resolución y detalles. Se ejecutaron las tres solicitudes anunciadas, sin reintentos, con el bridge aislado 8091 y ComfyUI 8188. No se modificaron código, grafos, modelos, encoder BF16, dependencias ni routing. Parámetros comunes: seed 42, cuatro pasos, guidance 1, una imagen por solicitud.

## Resultados locales

| Caso | Output | Solicitud / job Comfy (s) | Pico global muestreado / margen (MiB) | Revisión visual informal |
|---|---|---|---|---|
| Continuidad: taza original, atardecer y vapor | 512×512 | 14,141 / 12,230 | 11687 / 601 | Identidad y encuadre conservados; luz dorada y vapor visibles, este último muy enfatizado. |
| T2I: reloj, llave y tejido fino | 768×1376 | 12,156 / 11,134 | 11963 / 325 | Objetos completos, fibras, arañazos y dos agujas visibles. Cumplimiento parcial: inscripción inventada pese a pedir ausencia de letras. |
| Edit: tejido burdeos y eliminación de inscripción | 768×1376 | 20,547 / 18,973 | 11588 / 700 | Cambio de tejido y retirada de letras logrados; reloj, llave, posiciones y detalle visualmente conservados. |

Los tres casos devolvieron HTTP 200, PNG de las dimensiones pedidas e historial Comfy `success`, sin errores registrados. La continuidad usó como raíz la taza roja original, no la edición azul intermedia. Ambas ediciones utilizaron una referencia escalada a 1 MP por el grafo existente. La tercera tomó como referencia la imagen de reloj de la segunda prueba.

Se conserva el fallo semántico del T2I: no se repitió su generación ni se acepta gracias a un fallback. Tras comprobar que el prompt enviado contenía la restricción, se amplió el encargo de la tercera edición ya prevista para retirar esa inscripción además de cambiar el color del tejido. Esa edición demuestra una corrección en un caso concreto, no fiabilidad general contra pseudotexto.

## Evidencia y límites

[Registro JSON](validation/flux-klein-4b-resolution-details-2026-10-07.json): solicitudes exactas, hashes iniciales de los tres assets y binario, prompt IDs, tiempos, muestras de GPU, paths/SHA de imágenes, revisión visual y controles finales. Hash de cada PNG devuelto igual al original Comfy; dimensiones e historiales revalidados al cierre.

Artifacts locales bajo `D:\Apps\MPT-worktrees\image-model-routing-modernization\local_image_stack\experiments\bridge\target\resolution-details-2026-10-07`, subcarpetas `continuity_512`, `detail_t2i_768x1376`, `detail_edit_768x1376`, cada una con `result.png`. Originales en `C:\Users\JAVIER\ComfyUI-Installs\ComfyUI\ComfyUI\output`, nombres `MPT_EXPERIMENT_KLEIN4B_00003_.png` a `00005_.png`. Harness y artifacts ignorados por Git; conservarlos antes de archivar el worktree.

Mediciones de GPU globales, muestreadas aproximadamente cada segundo, con 12288 MiB totales: no son picos exactos ni memoria por modelo. Baselines distintos (10255, 10203 y 9282 MiB), caches y otros procesos sin controlar. Los tiempos tampoco constituyen una comparación de rendimiento controlada. Sin OOM registrado en estos casos; el margen mínimo observado de 325 MiB impide garantizar cargas mayores o multi-ref. No se probaron otras resoluciones en esta serie.

Inspección visual individual, sin métricas de invariancia geométrica, exactitud de reloj, evaluación ciega ni repetibilidad. Hay detalles finos visibles, pero no certificación general de calidad. Son pruebas funcionales del bridge/modelo; falta el caller real de MPT y su pipeline completo.

## Cierre y siguiente tarea

Cola Comfy vacía; instancias experimentales cerradas y 8091 libre. Servicios originales responden: 8080 health 200, 8090 raíz 404 (liveness), 8188 system_stats 200. Hashes del source externo del bridge y HEAD estable `6d27ba4963ffe469d635db71eaeec506a8ff4b61` conservados. No se cambiaron servicios originales ni se publicó vídeo. Candidato sigue `planned`.

Solo cambian documentación y evidencia: no se repiten los 173 tests Python y uno Rust del checkpoint de implementación. Controles pertinentes de esta fase: hashes, dimensiones, parámetros, historial, revisión visual, limpieza, JSON, enlaces, diff y secretos.

Siguiente tarea concreta: prueba controlada de dos referencias a 512×512 para validar roles/identidad/estilo con vigilancia de memoria; después abordar multi-ref a resolución objetivo y caller MPT experimental con smoke de dos escenas. Estas fases siguen pendientes, sin promoción automática del candidato.
