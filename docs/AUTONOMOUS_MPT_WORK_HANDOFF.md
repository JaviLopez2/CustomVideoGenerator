# Continuación autónoma de MPT — 2026-10-09

El usuario autoriza avanzar de forma continuada según el plan experimental, ejecutar las pruebas y mejoras necesarias y resolver decisiones rutinarias sin pedir otro «sigue». Su límite declarado es el uso de Codex. Se ha creado un objetivo persistente **activo** en este chat; los checkpoints no terminan el objetivo ni requieren permiso para la siguiente tarea.

## Operación y permisos

Worktree `D:\Apps\MPT-worktrees\image-model-routing-modernization`, rama `factory/image-model-routing-modernization`. Base de esta ejecución `f36b2a148b0725d387bb6c54e9eadef3ad5da4fa`, status/diffs inicialmente vacíos, diez worktrees comprobados. Conservar cambios existentes; commits y push normal solo en experimental. MPT estable protegido, sin force-push, auto-merge ni publicación de vídeos. No interpretar autonomía como evidencia perceptual ni modificar un gate para eludir incertidumbre.

La sesión efectiva tiene `workspace-write` y revisión automática de escalaciones. Los accesos de lectura y las escrituras concretas autorizadas en metadatos Git/input Comfy funcionan. No se cambia configuración global, ACL o permisos permanentes; no hace falta activar acceso completo para las operaciones comprobadas. Si la revisión automática rechaza una acción, intentar una alternativa segura y documentar el bloqueo antes de pedir intervención. Un ajuste de la interfaz solo será necesario si aparece un bloqueo efectivo.

Dejar Windows despierto y Codex abierto para trabajar con estos archivos y servicios locales. Un objetivo activo puede continuar entre turnos; pausas, límites de cuenta y bloqueos reales siguen siendo posibles. [Objetivos de Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex), [operación local y tareas programadas](https://learn.chatgpt.com/docs/automations?surface=app). Se usa la continuación del objetivo, sin crear otra ejecución periódica concurrente del mismo trabajo.

No preguntar por decisiones rutinarias de prueba, documentación o checkpoint. Para una etiqueta que necesite revisión humana independiente, conservar `pending` y avanzar con tareas que no dependan de ella. La aprobación previa «La zona cian es adecuada» revisa únicamente la región de la máscara, no futuros resultados, counts de positivos ni producción. Los límites de cada cohorte y los cambios de metodología se declaran antes de ejecutar; los fallos se conservan.

## Resultado nuevo

[Edición enmascarada ejecutada](MUG_MASKED_EDIT_EXECUTION.md): una solicitud directa a8188, 512²/4 pasos/seed42, cero retries. Éxito técnico en 12,328s y conservación exacta fuera de máscara; el resultado sigue conectado y presenta un parche visible según inspección del asistente. Cohorte cerrada como control inutilizable; cero consultas a jueces. Esto no mide la capacidad de un juez.

## Próxima acción, sin otro permiso rutinario

Ejecutar la ablación offline fijada en [plan de retirada de referencia](validation/mug-masked-no-reference-plan-2026-10-09.json). Una nueva cohorte de una generación, cero retries, misma imagen/máscara/prompt/seed/latente/steps y composición. Única condición de modelo cambiada: conditioning sin ReferenceLatent. Un segundo SaveImage guarda el decode anterior a composición; instrumentación sin otro sampling. Comparar artefacto crudo/final y conservación. No cambia plantillas activas, deps, pesos o servicios.

Si también falla, cerrar esta hipótesis sin seguir ajustando prompts hasta acertar. Evaluar el siguiente trabajo útil del QA sobre artifacts retenidos y mantener incierta la sensibilidad estructural no validada. Si produce un negativo aparentemente adecuado, solicitar una sola revisión independiente de resultado y positivos, sin detener tareas independientes ni convertir la inspección del asistente en respuesta humana. Guardar checkpoints/handoff y continuar mientras el objetivo siga activo.
