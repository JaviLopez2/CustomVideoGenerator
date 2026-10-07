# Klein 4B: una edición con referencia

2026-10-07, base `a3d82a25e16ed301ed79f20ca0eb7c5bb357a34b`. El usuario pidió la siguiente prueba propuesta: single-reference edit. Se comprobó que el turno interrumpido no dejó artifacts de edición, cola ocupada ni proceso en 8091. Una única generación, sin reintento. [Evidencia completa](validation/flux-klein-4b-gpu-single-ref-512-seed42-2026-10-07.json).

Entrada: PNG de la taza roja del T2I anterior, hash verificado y copiado sin sobrescritura a `ComfyUI\input\MPT_KLEIN4B_SMOKE_RED_512_SEED42.png`. Una referencia `identity_reference`. Se pidió cambiar solo rojo a azul profundo y conservar forma/asa/posición/escala, mesa/ventana/fondo/cámara/luz. Alias `flux-klein-4b-edit-exp`, output512×512, seed42, steps4, guidance1, n1. El grafo existente escala la referencia a **1 MP**; 512×512 describe la salida, no toda la carga de referencia.

Assets y binario rehashados; cola vacía antes de enviar. Bridge experimental `--serve-gpu` 8091, una sola solicitud. Resultado técnico **PASS**: HTTP200, PNG512×512 válido, una entrada nueva de historial con el grafo exacto, status success/completed, sin errores registrados.

| Medida local | Resultado |
| --- | --- |
| Solicitud completa | 14,219 s |
| Job Comfy start→success | 13,926 s |
| Baseline VRAM global | 4264 MiB |
| Pico global muestreado | 11756/12288 MiB, 14 muestras a intervalo objetivo 1 s |
| Margen global observado en el pico | 532 MiB |
| Cola final | 0 running, 0 pending |

Prompt ID `75b9e21c-cbef-4dbc-89fb-fc21b30df506`. SHA imagen `a245930e585f44b031f82704c66793016d67e037746937fa2976d7c982fadf61`, igual al original Comfy. Copia local: `D:\Apps\MPT-worktrees\image-model-routing-modernization\local_image_stack\experiments\bridge\target\gpu-single-ref-512-seed42-2026-10-07\klein4b-edit-blue-mug-512-seed42.png`; original `C:\Users\JAVIER\ComfyUI-Installs\ComfyUI\ComfyUI\output\MPT_EXPERIMENT_KLEIN4B_00002_.png`. Request/logs junto a la copia local. Binarios/artifacts ignorados por Git; conservar antes de archivar el worktree.

Revisión visual comparada: cambio a azul logrado, una taza completa, geometría/asa/posición/escala y mesa/ventana/fondo/encuadre parecen bien conservados; sin texto/watermark apreciable. **PASS visual informal para este caso**, sin afirmar invariancia exacta de píxeles/geometría, puntuación ciega o repetibilidad.

Bridge experimental cerrado y 8091 libre. Servicios originales 8080 health200, 8090 raíz404, 8188 system_stats200; estable HEAD `6d27ba4963ffe469d635db71eaeec506a8ff4b61` intacto. Sin cambios de configuración/routing/fallback/QA, dependencias o workflows, reinicios, más descargas o publicación. Encoder BF16 conservado.

El pico es global y muestreado; incluye otros procesos, caches previas sin reset. No comparar causalmente estos tiempos con el T2I como benchmark controlado. Margen pequeño para esta carga: no demuestra viabilidad de 2–3 refs o resolución objetivo. Candidato sigue `planned`; no se valida un vídeo MPT por esta edición.

El usuario preguntó si conviene algo más complejo. Sí, después de este gate: conservar identidad/encuadre con avance de un estado visible; luego combinar 2–3 referencias y resolución objetivo. Propuesta concreta para la siguiente prueba autorizada: misma taza/mesa/ventana desde la raíz original, cambiar iluminación a atardecer y añadir vapor visible, sin cambiar geometría/composición. Cambios y conservación evaluables por separado. Esa pregunta no desencadenó otra generación.

Solo documentación/evidencia en este checkpoint; no se repiten tests de código sin cambios. Checks pertinentes: hashes/PNG/dimensiones/historial exacto, comparación visual, sensores/cola/servicios, cierre del proceso, JSON/diff/enlaces/secretos.
