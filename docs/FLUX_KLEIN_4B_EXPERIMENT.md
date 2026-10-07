# Klein 4B Distilled FP8: contrato experimental offline

Fecha: 2026-10-07. Base: `37ef653e8d47483e997d6b8fb52ebc1a5ba1732d`. Esta fase implementa únicamente aliases, manifiesto y contratos/tests offline del plan entregado por el usuario. No activa modelos, routing, workflows ni servicios.

## Aislamiento y assets

El módulo `local_image_stack/experiments/klein4b.py` es independiente de producción; no importa MPT, Torch, ComfyUI ni un cliente HTTP, no descarga y no envía solicitudes. Los aliases se registran solo en su mapa experimental:

| Alias | Referencias | Binding planificado |
| --- | --- | --- |
| `flux-klein-4b-t2i-exp` | Ninguna | T2I 4B Distilled FP8 |
| `flux-klein-4b-edit-exp` | 1–3 | Edit 4B Distilled FP8 |

No se reutiliza `flux-klein-precision` (9B KV). El resolver rechaza otros aliases y checkpoints; la admisión comprueba también el checkpoint del grafo API, para que un manifiesto 4B no oculte un loader 9B.

[Manifiesto versionado](validation/flux-klein-4b-assets.json): DiT `flux-2-klein-4b-fp8.safetensors`, encoder `qwen_3_4b.safetensors`, VAE `flux2-vae.safetensors`. Fuentes exactas y licencias declaradas incluidas. Estado `planned`; hashes de todos los pesos y grafos nulos, revisiones de ejecución nulas. El encoder ya observado localmente no se marca verificado por coincidir su nombre.

El [checkpoint FP8 oficial](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8) declara Apache 2.0. El [encoder Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) declara Apache 2.0; BFL declara Apache 2.0 para el [autoencoder FLUX.2](https://github.com/black-forest-labs/flux2#flux2-autoencoder). La identidad/licencia de los archivos locales exactos sigue pendiente. Los [templates ComfyUI](https://github.com/Comfy-Org/workflow_templates/blob/main/LICENSE) son MIT, no la licencia del modelo.

Los bindings apuntan a templates oficiales de interfaz, no a grafos API instalados. El [template T2I](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux2_klein_text_to_image.json) expone otras variantes: se debe seleccionar explícitamente Distilled FP8 antes de exportar. El [template Edit Distilled](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_flux2_klein_image_edit_4b_distilled.json) también debe exportarse, parametrizar slots y eliminar conexiones a imágenes demo. No se copiaron, convirtieron ni modificaron workflows en esta fase.

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

Siguiente tarea concreta: exportar y revisar grafos API T2I/Edit en una carpeta experimental, sin pesos nuevos ni ejecución, preservando orden/roles y desconectando demos; reconciliar este contrato con las sustituciones reales del bridge. Resolver por separado la regresión preexistente de capitalización antes de declarar todo el gate offline aprobado.

Con autorización posterior: identificar/hashar assets exactos y revisiones; luego validación GPU gradual (load, T2I, single-ref, temporal, 2–3 refs, escena aislada, smoke de dos escenas, A/B). No se ejecutó ninguna etapa. Medir en la 3060 OOM/estabilidad, repetibilidad, pico VRAM y tiempos; cifras de 5090 o tamaños en disco no garantizan 12 GB. Promoción requiere gates legal/assets, técnico, semántico y rendimiento, más preservación de identidad, avance temporal y fidelidad a referencias. Descargas, generaciones y cambios activos siguen requiriendo un encargo específico.
