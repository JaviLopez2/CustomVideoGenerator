# Continuación autónoma de MPT — 2026-10-09

El usuario autoriza avanzar de forma continuada según el plan experimental, ejecutar las pruebas y mejoras necesarias y resolver decisiones rutinarias sin pedir otro «sigue». Su límite declarado es el uso de Codex. Se ha creado un objetivo persistente **activo** en este chat; los checkpoints no terminan el objetivo ni requieren permiso para la siguiente tarea.

## Operación y permisos

Worktree `D:\Apps\MPT-worktrees\image-model-routing-modernization`, rama `factory/image-model-routing-modernization`. Base de esta ejecución `f36b2a148b0725d387bb6c54e9eadef3ad5da4fa`, status/diffs inicialmente vacíos, diez worktrees comprobados. Conservar cambios existentes; commits y push normal solo en experimental. MPT estable protegido, sin force-push, auto-merge ni publicación de vídeos. No interpretar autonomía como evidencia perceptual ni modificar un gate para eludir incertidumbre.

La sesión efectiva tiene `workspace-write` y revisión automática de escalaciones. Los accesos de lectura y las escrituras concretas autorizadas en metadatos Git/input Comfy funcionan. No se cambia configuración global, ACL o permisos permanentes; no hace falta activar acceso completo para las operaciones comprobadas. Si la revisión automática rechaza una acción, intentar una alternativa segura y documentar el bloqueo antes de pedir intervención. Un ajuste de la interfaz solo será necesario si aparece un bloqueo efectivo.

Dejar Windows despierto y Codex abierto para trabajar con estos archivos y servicios locales. Un objetivo activo puede continuar entre turnos; pausas, límites de cuenta y bloqueos reales siguen siendo posibles. [Objetivos de Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex), [operación local y tareas programadas](https://learn.chatgpt.com/docs/automations?surface=app). Se usa la continuación del objetivo, sin crear otra ejecución periódica concurrente del mismo trabajo.

No preguntar por decisiones rutinarias de prueba, documentación o checkpoint. Para una etiqueta que necesite revisión humana independiente, conservar `pending` y avanzar con tareas que no dependan de ella. La aprobación previa «La zona cian es adecuada» revisa únicamente la región de la máscara, no futuros resultados, counts de positivos ni producción. Los límites de cada cohorte y los cambios de metodología se declaran antes de ejecutar; los fallos se conservan.

## Resultado nuevo

[Ablación posterior ejecutada y cerrada](MUG_MASKED_NO_REFERENCE_REPORT.md), base `4800f80`: una generación/6,140s, cero retries; retirar la referencia conserva fuera de máscara pero tampoco produce separación limpia. El defecto ya aparece en decode crudo. La línea de microedición se cierra sin otras generaciones para buscar un resultado favorable. La liberación de caché de Comfy, con cola vacía, resolvió un preflight de memoria sin reiniciar servicios.

[Edición enmascarada ejecutada](MUG_MASKED_EDIT_EXECUTION.md): una solicitud directa a8188, 512²/4 pasos/seed42, cero retries. Éxito técnico en 12,328s y conservación exacta fuera de máscara; el resultado sigue conectado y presenta un parche visible según inspección del asistente. Cohorte cerrada como control inutilizable; cero consultas a jueces. Esto no mide la capacidad de un juez.

## Comparación de forma completada

Implementación desde0746505930e23ddbb007c6eda0634fde9f821037 y publicada92ea66495ff39dfc9368791a0802e6b54b183c49. Observador/runner aislados,51 nuevos tests y184 totales pasan7,34s/exit0/sin avisos; RED/GREEN y revisión sin hallazgos conservados. Fuentes sin cambio después de ese test. Cuatro cohortes/12 consultas completadas,0 retries/generaciones/descargas: ambos jueces omiten el gran cambio B en fotograma completo y lo distinguen en recorte, A/C sin cambio importante. [Informe](PAIRED_SHAPE_PROBE_REPORT.md) y [cierre](validation/paired-shape-closing-checks-2026-10-09.json).

Regiones previas+8px, mismo prompt/schema/decoding, exactos subconjuntos de píxeles RGB/RGBA; las cajas manuales no son un localizador automático. Contexto y resolución efectiva cambian juntos.3pares conocidos no validan gate/identidad o precisión general; raw/labels permanecen intactos y offline, Bmask excluida. Medias4,3–4,9s del diagnóstico y carga~4s separada, no QA completo/p95. Cuatro servidores propios8092 cerrados; app/pesos/defaults/gates/routing/plantillas/deps/estable intactos. Conservar crops/logs ignorados. SHA final de este checkpoint mediante Git/origin.

## Próxima acción, sin otro permiso rutinario

[Auditoría CPU](validation/temporal-caption-ambiguity-audit-2026-10-09.json) reproduce un fallo específico de state_check: «may have frost» pasa, presencia/ausencia contradictoria pasa, «might be smoke» falla sin certeza y ausencia anterior cualificada acredita progresión. Corregir de forma genérica con tests RED→GREEN, mantener fail ante negativo inequívoco y separar estado actual de progreso no demostrado; bump de VERSION invalida verdicts antiguos. Este parche está pendiente y no necesita servicios ni inferencia. La caché/selectividad ya existe, no rehacerla.

Después preparar contraste ROI con otra familia y controles de cobertura, ligados a fuentes antes de consultar. Sin relajar gates, inventar labels/counts de taza, reabrir la microedición cerrada o descargar modelos. Continuar autónomamente los pendientes verificables del plan; guardar checkpoints/handoff mientras el objetivo siga activo. No pedir otro «sigue» por checkpoint; no hace falta intervención humana para esta siguiente tarea CPU.
