# Puente privado de diagnóstico pareado — 2026-10-09

Base `5ad52e072412e16191036a6b5b7121dd93c9619c`, rama/worktree experimental limpio, diez worktrees. Turno anterior: progreso, adaptador/replay CPU de cuatro informes publicado. Objetivo completo de QA rápido y fiable sin cumplir. La autorización de autonomía del usuario permite ejecutar este diseño rutinario sin otra aprobación; ejecución nativa, revisión focal independiente con Cavecrew.

## Diseño e interfaces

Se amplía únicamente el punto privado existente de material. Alternativas descartadas: convertir pares en inventarios monoimagen perdería roles; importar scripts desde app acoplaría producción al harness; duplicar sus parsers/reconstrucción no aporta evidencia. Se usa un puente fino de datos con callbacks explícitamente inyectados al caller experimental.

Nuevo módulo `app/services/paired_visual_observation_diagnostics.py`:

- `diagnose(candidate, *, reference, previous, subject, contexts, observers) -> dict`: callbacks por `shape`/`cue`, misma firma `lookup(images, region_ids=..., subject=..., cue_query=...)` que el adaptador publicado. Contexto por tipo con `region_ids` ordenados, `subject` y `cue_query` solo para cue. Sin rutas en el contexto. No infiere sujeto/consulta de captions/estados ni sustituye una referencia/anterior ausente por el candidato.
- `finalize(diagnostic, candidate, *, reference, previous) -> dict`: después de QA/reintentos/postprocesado, comprueba las fuentes y candidato actuales contra los hashes capturados. Si cambia o falta cualquiera, conserva las observaciones anteriores en su etapa y deja las actuales unavailable. No reconsulta al proveedor.
- Solo admite el envelope del replay publicado, uncertain/unavailable, scores null, presupuestos cero y autoridad false. Para observaciones disponibles, comprueba protocolo, roles/source SHA/sujeto/consulta contra inputs reales del pipeline. Copia solo campos diagnósticos públicos. Fallo/objeto no serializable/salida inválida son unavailable y no interrumpen la escena.

Caller privado `_download_videos_openai_image_on_demand` añade `paired_visual_observers=None` y `scene_paired_observation_contexts=None`, sin configuración/UI/registro global. Defaults no leen/hashan diagnósticos. Cuando se inyecta:

1. Shape recibe la ruta local ligada por `comfyui_input` a `reference_images[0]` efectivamente enviado. El pack preparado guarda `local_path` por entrada; un campo superior de un archivo excluido no sirve como vínculo. Sin vínculo inequívoco, unavailable, sin adivinar carpeta por basename ni cambiar el selector/routing.
2. Cue recibe la última imagen aceptada/renderizada de la misma `continuity_key`, conservada solo para diagnóstico. No usa la raíz fija como anterior después de la segunda escena, ni cruza claves. El reinicio de fase existente limpia ese historial. Sin anterior, unavailable.
3. Captura observaciones después de selección inicial y antes de QA. Guarda `paired_visual_observation_diagnostic` en item y ledger. Finaliza después de QA/retries/color grading, adjunta al item final o deja motivo sin final en el ledger. No participa en selección, QA, retries, budgets o admisión; no sustituye scoped_qa ni altera store monoimagen.

## Ejecución y evidencia

1. Tests RED de bridge: callbacks explícitos, roles/sujeto/consulta/provenance, invalid/unavailable/omisiones, scores/autoridad/budgets inválidos, snapshots, imágenes ausentes o cambiadas durante/después de llamada y finalización sin reconsulta.
2. Implementación mínima y GREEN. Reutilizar el loader publicado en fixtures CPU, sin alterar sus helpers/protocolos/SHAs.
3. Tests RED/GREEN del caller: no-op por defecto, contratos/contextos inválidos no cambian la escena, referencia vs anterior en tres escenas, claves distintas/reset, matriz de QA pass/fail/uncertain/unavailable, incertidumbre no verifica Klein, cambios finales/retry invalidan evidencia y preservan decisiones históricas.
4. Suite relevante de material/continuidad/QA/monoimagen/bridge, revisión independiente, diff/AST/JSON/secret patterns. No repetir pruebas no afectadas para sumar counts.
5. Demostración CPU con archivos y callbacks retenidos: sujeto/pares reales, 0 inferencia/generación/HTTP/render real. No atribuir verdicts del pipeline simulado a mediciones de calidad. Checkpoint/handoffs/push normal, SHA local/remoto/status/estable.

Presupuesto de esta fase: 0 consultas a modelos, generaciones, descargas, control de servicios, dependencias y vídeos reales. Las generaciones/renders en tests son sustitutos offline. Las etiquetas humanas A/B/C y los datos históricos permanecen iguales. Estable/main/force-push/auto-merge protegidos.

## Focos de revisión y siguientes requisitos

Riesgos cubiertos por tests: un anterior de otra fase; confundir raíz/anterior; callback cambia bytes; retorno que pretende pass/admisión; diagnóstico de candidato anterior tras retry/color grading. La disponibilidad describe salida retenida y correspondencia actual, no verdad perceptual. Sin calibrated scores/umbral arbitrario/candidato elegido.

Después del puente: negativos geométricos válidos de otra familia y cantidad/estado con referencias independientes; errores/abstención/cobertura semántica y latencia de QA completo. No convertir éxito del bridge en selección o routing automático. Diseño revisado contra el punto privado existente y el encargo original: conserva separación identidad/estado/progresión, fail-closed, selectividad/cache ya implementados y presupuesto cero de esta entrega.
