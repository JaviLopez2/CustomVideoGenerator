# Klein 4B: caller MPT experimental

Integración opt-in en `app/services/klein4b_experimental.py` y `material.generate_images_openai`. No modifica configuración persistida, UI, routing por defecto ni el servicio estable. Requiere `openai_image_klein4b_experimental_enabled = true` como booleano en la configuración de ese proceso experimental. El endpoint aislado es `http://127.0.0.1:8091/v1/images/generations`.

## Contrato

- `model_override="flux-klein-4b-t2i-exp"`: cero referencias. `flux-klein-4b-edit-exp`: de una a tres, según el contrato offline; tres aún no están validadas con GPU.
- `route="standard"` y `route="precision"` representan calidad; ambas admiten T2I. El conditioning se registra aparte como `none`, `manual_reference` o `continuity_reference`.
- Referencias ya subidas a Comfy, en `reference_images`, con un `reference_info.reference_pack` de igual longitud y roles explícitos. Si se proporciona `reference_image`, debe coincidir con la primera referencia; no se reordena ni descarta silenciosamente ninguna.
- Roles MPT: `identity`, `detail`, `style`, `continuity`; se traducen a los cuatro roles del bridge. También se admiten sus nombres canónicos. `comfyui_input`, cuando aparece en el pack, debe coincidir con el slot. Un rol desconocido falla antes del dispatch.
- La raíz puede estar en cualquier slot. `temporal_progression=true` requiere raíz y `temporal_state`; no se conserva el estado previo cuando contradice el siguiente. Descripciones de evidencia y exclusiones de escena llegan al prompt positivo.
- `openai_image_klein4b_seed` controla la seed (42 por defecto experimental). Cuatro pasos, guidance 1 y una imagen. Se usan las reglas existentes de tamaño de MPT y se verifica que el output corresponda exactamente.
- Identidad de los assets verificada mediante SHA en el preflight de sesión. Por escena se comprueban presencia, nombre, tamaño y estado verificado, sin releer 13 GB en cada solicitud. El workflow se verifica por SHA. Esto no convierte el manifiesto `planned` en `ready`.

El caller devuelve `MaterialInfo` con modelo solicitado/efectivo, workflow y hash, prompt final, roles, conditioning, parámetros, tiempo y `qa_status=pending`. Esa devolución acredita generación; no aprobación visual. La normalización PNG de MPT cambia metadatos del contenedor: el harness comprueba igualdad de píxeles con el original Comfy.

## Fallos y QA

Cada intento Klein realiza un solo POST. Un fallo de bridge, bytes inválidos o tamaño incorrecto es explícito; no pasa automáticamente a 9B. La configuración histórica `flux-klein-precision` conserva su significado y código legacy.

El fallback hacia un alias 4B configurado explícitamente solo admite por ahora HTTP 404 que confirme ausencia de modelo/workflow (`unknown model`, `model not found`, `workflow not found`). Mantiene todas las referencias/roles y registra motivo/modelo primario/tiempos. Errores ambiguos, timeout, fallos semánticos, temporales o factuales no autorizan otra generación. OOM, fallos genéricos 5xx y recuperación de outputs inválidos no están habilitados en esta política inicial: requieren una clasificación más estructurada, no heurísticas permisivas.

En el bucle de escenas, el modelo efectivo identifica a Klein incluso cuando llegó por fallback. Cada candidato experimental necesita QA disponible con `status=pass` **y** `verdict=pass`; si hay progresión temporal, también necesita ese resultado temporal. QA deshabilitado, ausente o incierto rechaza la escena antes de renderizar/registrar una raíz aceptada. No se ejecuta reparación semántica automática para Klein; se conserva el artifact para diagnóstico. Los caminos y tests legacy de Qwen conservan su comportamiento.

La evidencia real mostró `gross status=pass` con `verdict=uncertain` para un reloj de tres agujas, y temporal `uncertain` para una taza enfriada. Esos resultados no cumplen el nuevo gate. Tampoco un `pass` del QA basado en captions garantiza exactitud geométrica fina: la promoción sigue bloqueada.

## Validación y límites

Suite final del área: **241 passed, 2 subtests passed**, incluyendo 42 casos nuevos del caller, transporte y bucle de escenas. [Log](validation/flux-klein-4b-mpt-regressions-2026-10-08.txt). Contratos y Rust nativo preflight: [61 passed](validation/flux-klein-4b-autonomous-baseline-2026-10-08.txt). No se modificaron tests históricos. La suite enfocada registra un paso intermedio de 40 casos; el agregado final incluye las adiciones posteriores.

Escenas reales desde el caller, multi-reference, comparación y límites: [informe de ejecución](FLUX_KLEIN_4B_AUTONOMOUS_REPORT.md). No se ejecutó un vídeo ni se acreditó un recorrido completo planner→selector→render con Klein. Antes de conectar selección automática Standard/Precision, hay que validar admisión factual/temporal y selección explícita del alias según conditioning. No basta cambiar un alias T2I por Edit ni tratar `precision` como sinónimo de Qwen.
