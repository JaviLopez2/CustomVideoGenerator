# Klein 4B Distilled FP8: contrato experimental offline

Fecha: 2026-10-07. Base del contrato inicial: `37ef653e8d47483e997d6b8fb52ebc1a5ba1732d`. La continuación sobre `d4d32c4` añade grafos API aislados y su adaptación offline; sus resultados se detallan al final. No activa modelos, routing, workflows ni servicios.

## Aislamiento y assets

El módulo `local_image_stack/experiments/klein4b.py` es independiente de producción; no importa MPT, Torch, ComfyUI ni un cliente HTTP, no descarga y no envía solicitudes. Los aliases se registran solo en su mapa experimental:

| Alias | Referencias | Binding planificado |
| --- | --- | --- |
| `flux-klein-4b-t2i-exp` | Ninguna | T2I 4B Distilled FP8 |
| `flux-klein-4b-edit-exp` | 1–3 | Edit 4B Distilled FP8 |

No se reutiliza `flux-klein-precision` (9B KV). El resolver rechaza otros aliases y checkpoints; la admisión comprueba también el checkpoint del grafo API, para que un manifiesto 4B no oculte un loader 9B.

[Manifiesto versionado](validation/flux-klein-4b-assets.json): DiT `flux-2-klein-4b-fp8.safetensors`, encoder `qwen_3_4b.safetensors`, VAE `flux2-vae.safetensors`. Fuentes exactas y licencias declaradas incluidas. Estado `planned`; los tres hashes locales están verificados tras la instalación autorizada, pero las revisiones de ejecución siguen nulas. No se admite ningún componente por nombre. Ver [preflight, plan e instalación](FLUX_KLEIN_4B_INSTALL_PLAN.md).

El [checkpoint FP8 oficial](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8) declara Apache 2.0. El [encoder Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) declara Apache 2.0; BFL declara Apache 2.0 para el [autoencoder FLUX.2](https://github.com/black-forest-labs/flux2#flux2-autoencoder). La identidad/licencia de los archivos locales exactos sigue pendiente. Los [templates ComfyUI](https://github.com/Comfy-Org/workflow_templates/blob/main/LICENSE) son MIT, no la licencia del modelo.

Inicialmente los bindings solo referenciaban templates oficiales de interfaz. El [template T2I](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux2_klein_text_to_image.json) expone otras variantes; el [template Edit Distilled](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux2_klein_image_edit_4b_distilled.json) contiene imágenes demo. La continuación reconstruye su topología nativa como grafos API locales, seleccionando Distilled FP8 y sustituyendo demos por placeholders; no los instala en servicios.

## Contrato implementado

`build_request` construye un envelope de inspección con `dispatch_allowed=false`. Su payload usa los campos del bridge: `model`, `prompt`, `seed`, `size`, `n=1`, `steps=4`, `guidance=1.0` y, cuando corresponde, `reference_image`, `reference_image_2`, `reference_image_3`. Mantiene orden y roles en una lista lateral; no deduplica o cambia roles silenciosamente. Rechaza packs duplicados o mayores de tres y modos incompatibles.

Roles: `continuity_anchor`, `identity_reference`, `factual_reference`, `style_reference`. Una raíz de continuidad identifica al mismo sujeto físico sin exigir conservar el estado anterior. El modo temporal exige raíz y estado solicitado, agrega una instrucción de avanzar a ese estado y rechaza las contradicciones explícitas del plan. Esto no constituye un analizador semántico completo de prompts arbitrarios.

**Límite de integración:** el bridge activo no recibe estos envelopes ni consume la lista lateral de roles. Su adaptación futura debe traducirlos a slots y conditioning, y aplicar steps/guidance en los nodos concretos de Flux. No está validado que los campos nuevos modifiquen un `Flux2Scheduler`/`CFGGuider` activo. El contrato offline no acredita esa integración.

`fallback_alias` permanece deshabilitado por defecto. Solo describe una política futura opt-in para errores técnicos confirmados, con referencias y sin una imagen válida generada. Los errores semánticos/temporales/factuales, timeouts ambiguos y errores desconocidos no habilitan fallback. El fallback productivo Qwen/Klein y las QA existentes permanecen intactos.

`require_ready` comprueba filenames, procedencia, licencia, SHA-256 de bytes locales, formato de grafo API, loaders 4B/encoder/VAE esperados, revisiones registradas y estado. En uso comercial rechaza componentes marcados `research_only`, `non_commercial` o sin scope admisible. No registra permisos globales ni certifica formatos de pesos, ejecución, memoria o calidad. Las fixtures de tests son bytes y grafos sintéticos; no son modelos ni workflows ejecutables.

## Validación real de esta fase

Python MPT portable 3.11.15; `MPT_RUN_INTEGRATION_TESTS=0`, `CUDA_VISIBLE_DEVICES=-1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. Sin cambios de dependencias.

- Contratos nuevos: **25 passed**. [Log](validation/flux-klein-4b-offline-tests-2026-10-07.txt).
- Contratos + cinco suites existentes de Qwen/continuidad/fallback: **112 passed**. [Log](validation/flux-klein-4b-regressions-2026-10-07.txt).
- Suite adicional `test_prompt_continuity_hardening.py`: **14 passed, 1 failed**. [Log](validation/flux-klein-4b-continuity-regressions-2026-10-07.txt). El test `test_continuity_without_state_keeps_natural_language_not_group_id` busca `same glyph on the tile` y recibe `Same glyph on the tile`. `git diff --exit-code` contra la base confirma que `llm.py`, `material.py` y ese test no cambiaron. No se modificó el test ni producción; el gate de todas las regresiones permanece pendiente.
- Parsing AST de ambos archivos Python correcto. Ruff no está disponible en el intérprete; no se instaló. Revisión de diff y secretos antes del checkpoint.

## Promoción y siguiente fase

No promover el candidato ni modificar fallback por estos resultados. La separación futura propuesta entre quality tier (Standard/Precision) y conditioning (none/manual/continuity) queda como arquitectura documental; no se implementa en el routing activo.

La tarea siguiente al contrato inicial era preparar grafos API T2I/Edit aislados y reconciliarlos con el bridge. Esa tarea queda documentada a continuación. La regresión preexistente de capitalización sigue abierta, sin cambiar los tests actuales de Qwen/continuidad.

Con autorización posterior: identificar/hashar assets exactos y revisiones; luego validación GPU gradual (load, T2I, single-ref, temporal, 2–3 refs, escena aislada, smoke de dos escenas, A/B). No se ejecutó ninguna etapa. Medir en la 3060 OOM/estabilidad, repetibilidad, pico VRAM y tiempos; cifras de 5090 o tamaños en disco no garantizan 12 GB. Promoción requiere gates legal/assets, técnico, semántico y rendimiento, más preservación de identidad, avance temporal y fidelidad a referencias. Descargas, generaciones y cambios activos siguen requiriendo un encargo específico.

## Continuación: grafos API y adaptador offline

Base `d4d32c4bedce37b1d0bbc214a63e736d9b11e4f9`, rama experimental limpia; fetch confirmó `0 0` respecto a origin. Grafos en `local_image_stack/experiments/workflows/`, fuera de las carpetas cargadas por el bridge. Se reconstruyeron desde los nodos de los templates oficiales, no mediante exportación desde una interfaz ni desde el workflow 9B KV. Se conserva el aviso MIT upstream. `.gitattributes` local fija LF para conservar sus hashes al hacer checkout en Windows.

T2I: 13 nodos, Euler, 4 pasos, CFG 1, UNET 4B FP8 directo, sin FluxKVCache, encoder Qwen3-4B tipo `flux2`, VAE Flux2. Edit: 18 nodos como plantilla de una referencia, con escala `nearest-exact` a 1 MP y codificación VAE. A diferencia del template UI, las dimensiones de salida proceden del tamaño solicitado, no de la primera referencia. La escala de referencia permanece en 1 MP: no es una optimización medida para 12 GB.

`klein4b_graph.prepare_graph` verifica SHA-256 y binding de la plantilla, reutiliza el contrato de intención y materializa exactamente 1–3 bloques de referencia. Cada bloque encadena el mismo latent a conditioning positivo y negativo, conservando orden. Sin referencias no hay ningún bloque de edición. Se fijan explícitamente seed, dimensiones, batch 1, steps 4 y CFG 1. Los roles se expresan en el prompt ordenado; todos los loaders se titulan `Subject Reference N` para evitar que el bridge redirija el rol de estilo a su campo legacy `style_reference_image`.

Referencias: filenames relativos ya disponibles en el input de Comfy, no URL, base64 ni rutas absolutas. El adaptador rechaza traversal y no sube archivos. Los placeholders no son imágenes demo y no se consideran archivos existentes. Envelopes conservan `dispatch_allowed=false`; el grafo resultante es material de inspección, no una autorización de ejecución. El módulo no contiene clientes HTTP ni imports de producción.

Contraste con `local_image_stack/bridge/comfyui.rs`: sustituye seed en RandomNoise, tamaño en EmptyFlux2LatentImage/Flux2Scheduler, texto en CLIPTextEncode y filenames por título. No adapta steps de Flux2Scheduler ni CFGGuider, ni poda cadenas ReferenceLatent como hace con slots Qwen. El adaptador aislado cubre esos bindings offline; no se conecta al Rust activo y no acredita que el servicio cargue estos aliases. La futura integración debe elegir explícitamente materialización por solicitud o workflows por número de referencias; copiar una plantilla estática al bridge actual no resuelve multi-ref ni slots ausentes.

Validación real: **126 passed** en contratos y las cinco suites enfocadas existentes ([log](validation/flux-klein-4b-api-tests-2026-10-07.txt)); incluye 14 casos nuevos de grafos. El test experimental de alias ahora comprueba checkpoint/ruta: buscar `9b` en todo el JSON daba un falso positivo en un hash SHA-256. No se alteró ningún test de `test/services/` ni producción. Suite adicional de continuidad: **14 passed, 1 failed**, mismo fallo preexistente de capitalización ([log](validation/flux-klein-4b-api-continuity-2026-10-07.txt)). El gate completo permanece abierto.

GET `/object_info` y revisión local: clases registradas, campos requeridos y tipos de enlaces compatibles en ambas plantillas ([evidencia](validation/flux-klein-4b-api-schema-2026-10-07.json)). Admisión de archivos pendiente: DiT 4B y VAE no aparecen en los loaders; encoder aparece sin identidad verificada. El placeholder Edit tampoco es un input real. HEAD de fuente Comfy `73c9bad4d21e7addbe1d13bc92eee0f1431b017d` es observación de disco, no revisión certificada del proceso. No se envió POST ni se cargaron nodos/modelos.

Siguiente tarea acotada: diagnosticar y acordar la corrección del gate preexistente de continuidad sin rebajar su exigencia semántica. Después, con encargo específico, verificar procedencia/hashes del encoder disponible y planificar instalación de DiT/VAE y una prueba GPU mínima. Siguen pendientes admisión de assets, binding del bridge activo, ejecución, memoria, calidad y promoción.

## Continuación: corrección del gate histórico

Base `de11868`. El helper del planner normaliza ahora el prefijo gramatical `same`/`the same` a `The same`, preservando la identidad, nombres propios y eliminación de duplicados. El cambio se limita a `app/services/llm.py` de este worktree experimental; no se desplegó. Tests existentes de Qwen/continuidad intactos; se añaden diez casos de planner con LLM simulado en `test/test_continuity_phrase.py`.

Resultados nuevos: **25 passed** en gate histórico + nuevos casos ([log](validation/continuity-prefix-focused-2026-10-07.txt)); **151 passed** al incluir contratos Klein y cinco suites relacionadas ([log](validation/continuity-prefix-regressions-2026-10-07.txt)). El fallo histórico documentado arriba está resuelto en esta continuación. No se ejecutó toda la suite del repositorio ni generación GPU. Los gates de assets, integración, calidad y rendimiento permanecen pendientes; candidato `planned`, sin cambios en manifiesto/grafos/bridge. Siguiente tarea: verificar el encoder existente y preparar plan de assets faltantes, antes de autorizar descargas o ejecución.

## Continuación: encoder verificado y plan de assets

Base `57a5747`: SHA-256 y tamaño del encoder existente coinciden con Comfy-Org en revisión fijada. Solo su hash local queda verificado; DiT/VAE mantienen hashes locales nulos y ahora tienen hashes esperados/revisiones upstream para una instalación posterior. Descarga pendiente: 4,41 GB. VAE Comfy y VAE Diffusers BFL coinciden en LFS; se documenta licencia del componente separada de la tarjeta del repositorio. [Plan concreto](FLUX_KLEIN_4B_INSTALL_PLAN.md), [evidencia](validation/flux-klein-4b-asset-preflight-2026-10-07.json) y [39 tests aprobados en esta fase](validation/flux-klein-4b-asset-preflight-tests-2026-10-07.txt). Sin descargar pesos, activar aliases ni ejecutar GPU; `planned` permanece.

## Continuación: descarga autorizada completada

Sobre `99d6abd`, instalados DiT y VAE del plan, con tamaño/SHA-256/cabecera verificados antes de renombrar parciales. Encoder BF16 rehashado y conservado; no hay mediciones que justifiquen sustituir la base oficial prevista. [Evidencia](validation/flux-klein-4b-install-2026-10-07.json), [39 tests aprobados](validation/flux-klein-4b-install-tests-2026-10-07.txt). Los tres componentes tienen hash local verificado, sin marcar candidato `ready`.

ComfyUI no responde al GET posterior en 8188 (conexión rechazada), por lo que inventario vivo e integración siguen pendientes. No se iniciaron servicios ni se activaron aliases, modificaron grafos o ejecutó GPU. La instalación no demuestra que el conjunto quepa en 12 GB ni certifica calidad/latencia. Siguiente fase: integración experimental y, con autorización específica de servicio/GPU, inventario vivo y carga mínima.

Recheck posterior a `b3e1191`: ComfyUI responde y lista los tres componentes, bridge responde en su raíz y MPT health pasa. Inventario vivo ya comprobado; conexión rechazada anterior histórica. Sin inicio/reinicio ni inferencia por el agente. Integración, revisiones efectivas y GPU siguen pendientes.

## Continuación: bridge nativo experimental validado sin GPU

Base `f38c63e`: variante Rust compilable en `local_image_stack/experiments/bridge`, con las dos plantillas 4B, aliases exclusivos, materialización de 0–3 refs y roles/temporal explícitos. Hook con feature solo en snapshot local, fuera del servicio externo; datos de source/código modificado preservados. [README y modos](../local_image_stack/experiments/bridge/README.md). Compilación offline/locked, sin nuevas dependencias globales ni descargas.

173 tests Python (22 nativos) y 1 Rust aprobados. Preview HTTP efímero 8091 lista los aliases y bloquea generación con 403; CLI y HTTP producen grafos equivalentes al adaptador Python. Proceso cerrado; servicios originales intactos. El modo `--serve-gpu` está preparado pero no ejecutado. No hay evidencia nueva de inferencia/memoria/calidad ni promoción. Siguiente fase: T2I GPU mínimo expresamente autorizado, después edición y caller MPT experimental; roles y endpoint deben incorporarse explícitamente al caller antes de escena/smoke.
