# Klein 4B: una prueba GPU T2I mínima

Fecha 2026-10-07. Base `066fcdddfdc86d5dcae5718d3b3baadbab769cdd`. El usuario autorizó explícitamente una única prueba T2I 512×512, 4 pasos, seed 42, mediante el bridge experimental. No hubo reintentos ni más generaciones. [Registro completo de la prueba](validation/flux-klein-4b-gpu-smoke-512-seed42-2026-10-07.json).

## Preparación y solicitud

Worktree limpio y fetch sin divergencia. Cola Comfy vacía comprobada antes y justo antes del POST. Los tres assets se rehasharon y coinciden con las revisiones fijadas. Binario experimental SHA-256 `7f8d125f3de758f6c65e7f06bcb43a427c04dec333ba98d386a51af4451d6a85`, igual al artifact compilado registrado para el código de `066fcdd`.

Bridge lanzado solo para esta prueba en `127.0.0.1:8091 --serve-gpu`, con polling y sin WebSocket; backend Comfy 8188. Alias `flux-klein-4b-t2i-exp`, size `512x512`, seed `42`, steps `4`, guidance `1.0`, n `1`, ninguna referencia. Prompt: una única taza roja de cerámica, completa en cuadro, sobre una mesa clara junto a una ventana, luz natural suave y sin texto/watermark. El JSON exacto está en la evidencia y en el directorio local de artifacts.

Runtime declarado por Comfy: versión `0.37.0`, Python `3.13.12`, PyTorch `2.12.1+cu130`, RTX 3060 de 12288 MiB según nvidia-smi. Flags observados: `--disable-async-offload`, `--disable-pinned-memory`. HEAD de la carpeta fuente se registra aparte; no se certifica como commit cargado por el proceso. No se cambió configuración, flags ni dependencias.

## Resultado medido localmente

| Comprobación | Resultado |
| --- | --- |
| Solicitudes de generación | 1, sin reintento |
| Respuesta del bridge | HTTP 200, una imagen PNG válida 512×512 |
| Tiempo de solicitud completa | 10,109 s |
| Tiempo Comfy entre execution_start/execution_success | 8,672 s; incluye el trabajo del job, no solo denoising |
| Historial Comfy | `success`, `completed=true`, sin errores registrados |
| VRAM global antes | 4424 MiB |
| Pico global muestreado | 11433 MiB, 10 muestras, intervalo objetivo 1 s |
| Margen global observado en ese pico | 855 MiB de 12288 MiB |
| Cola al finalizar | 0 running, 0 pending |

Prompt ID `d9d6b7c4-0e0a-4f2b-91ac-21064cb32565`; una única entrada nueva de historial con el grafo exacto esperado. La imagen devuelta por el bridge coincide en SHA-256 con el PNG original de Comfy: `16c94d6f649e693492a47a39a48e35f0ccede34f060c4e9031e385accf10ec93`.

Inspección visual del PNG guardado: una taza roja completa, mesa de madera y ventana visibles, sin texto ni watermark apreciable. Es una revisión informal de una imagen; no es QA de identidad, continuidad, fidelidad factual, comparación ciega ni prueba de repetibilidad.

## Artifacts y cierre

Imagen local: `D:\Apps\MPT-worktrees\image-model-routing-modernization\local_image_stack\experiments\bridge\target\gpu-smoke-512-seed42-2026-10-07\klein4b-t2i-512-seed42.png`. Original: `C:\Users\JAVIER\ComfyUI-Installs\ComfyUI\ComfyUI\output\MPT_EXPERIMENT_KLEIN4B_00001_.png`. Request y logs del proceso en el mismo directorio local de la copia. Artifacts binarios ignorados por Git; evidencia textual versionada. Conservarlos antes de archivar/limpiar el worktree.

Se cerró únicamente el bridge experimental creado por el agente y se comprobó que 8091 quedaba libre. Comfy y los servicios originales siguen respondiendo: 8188 system_stats 200, 8090 raíz 404, 8080 health 200. No se vaciaron caches/modelos de Comfy ni se reiniciaron servicios. MPT estable conserva HEAD `6d27ba4963ffe469d635db71eaeec506a8ff4b61`. Sin routing/fallback/QA nuevos ni publicación.

## Conclusión y siguiente tarea

**PASS de esta prueba T2I mínima**: pipeline experimental de solicitud, carga/ejecución y devolución de imagen funciona para este caso a 512×512, con encoder BF16 conservado. El margen global observado es pequeño; el pico es muestreado e incluye otros procesos. No hay medida exacta por modelo ni presupuesto demostrado para `768x1376`, edición o referencias. El estado previo de caches no se controló; no convertir estos tiempos en benchmark A/B o garantía de latencia.

Candidato completo sigue `planned`: no se valida promoción, calidad comparativa, reproducibilidad o smoke MPT de dos escenas. Siguiente tarea acotada propuesta: single-reference edit a 512×512 usando esta imagen como referencia y un cambio visible concreto, con autorización específica para una nueva generación GPU. Después, continuidad temporal/multi-ref y resolución objetivo en fases separadas; finalmente caller MPT experimental con roles y smoke de dos escenas. No ejecutar ninguna de esas fases por este permiso de una sola prueba.

Solo se añadió evidencia/documentación; no se repitieron los 173 tests Python + 1 Rust del checkpoint anterior. Comprobaciones pertinentes aquí: identidad de assets/binario, grafo en historial, PNG/dimensiones/hash original, inspección visual, sensores, cola y liveness; JSON/diff/enlaces/secretos antes del commit.
