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

## Parche temporal completado

Desde417dac34f5367c58412a0722f509ff3dbb2fbb39, state_check abstiene menciones cualificadas/contradictorias, no acredita progresión desde anterior ambiguo y conserva negativos/omisión inequívocos. VERSIONvisual-qa-3 invalida las claves existentes v2.37 nuevas regresiones CPU y186 tests finales pasan6,55s/exit0/sin avisos. Revisión independiente detectó corte de negación en saltos de línea; RED4 adicional, corrección y revisión final sin hallazgos. [Informe](TEMPORAL_CAPTION_AMBIGUITY_REPORT.md) y [cierre](validation/temporal-caption-closing-checks-2026-10-09.json).0 nueva inferencia/generación/GPU/descarga/servicio; app modifica solo ese parser y versión, sin modelos/defaults/gates/routing/plantillas/deps/estable. Texto léxico no certifica verdad visual ni resuelve toda negación. SHA final por Git/origin; pruebas anteriores de forma siguen separadas.

## Replay temporal y negación v4 completados

Desde d636da6039089694aed7a6825d141a33a8a4ec57,3casos archivados mantienen uncertain v2/v3/v4: exactos captions/OD/contratos/SHA, no nueva extracción ni cambio de labels.7desacuerdos en10controles literales v3 corregidos por state_check v4; ausencia posterior/contracciones/freeof/dobles y cache invalidada, sin reglas por objetos.30 nuevas regresiones/216 finales pasan6,67s/exit0/sin avisos; revisión encontró límites de modificadores, RED6 y cierre sin hallazgos. [Informe](TEMPORAL_CAPTION_REPLAY_REPORT.md), [checks](validation/temporal-negation-closing-checks-2026-10-09.json).0 nueva inferencia/generación/GPU/descarga/deps/servicio/pesos/defaults/routing/workflows/estable. Parser léxico no devuelve la información que falta en el caption ni certifica verdad visual. SHA final por Git/origin.

## Preparación de regiones completada

Desde35059e1, ocho recortes finales source-bound con píxeles/modo exactos y metadata auxiliar descartada; cuatro llaves byte-idénticas al histórico, dos tazas contained y controles partial/disjoint. Cajas anteriores+8px, no gold humano, cobertura rectangular no prueba objeto completo. Revisión tRNS reproduce pérdida de transparencia y se corrige rechazando el formato no soportado.32 nuevas pruebas/83 finales pasan0,39s/exit0/sin avisos; revisión final sin hallazgos. Dos cohortes CPU/8outputs cada una, todos v2 idénticos; helper/plan/resultados originales preservados. [Informe](VISUAL_REGION_PREPARATION_REPORT.md), [cierre](validation/visual-region-preparation-closing-checks-2026-10-09.json).0 nueva inferencia/generación/GPU/descarga/servicio/app/modelos/defaults/gates/routing/deps/estable; SHA final por Git/origin.

## Contraste ROI cross-family completado

Desde3907cd8, runner v2 neutral/source-bound preflight y33tests nuevos/116 finales pasan2,00s/exit0/sin avisos, review sin hallazgos; protocolo humano v1 compatible.6consultas reales a modelos existentes,0retry/generación/descarga: ambos not_observed en2pares de bytes idénticos y1recolor retenido,4consistencias +2observaciones sin gold humano/correctness. Todos diagnosticuncertain/sin identidad/admisión; partial/fondo0HTTP, inputs reconstruidos antes de cada envío.2PID propios cerrados/ausentes y8092libre; app/modelos/gates/routing/deps/compartidos/estable intactos. Medias4,703/4,168s/carga~4s, cache difiere/no QA completo. [Informe](CROSS_FAMILY_ROI_PROBE_REPORT.md), [cierre](validation/cross-family-roi-closing-checks-2026-10-09.json); SHA final por Git/origin.

## Próxima acción, sin otro permiso rutinario

Inspeccionar los3estados temporales ya conservados y sus contratos, sin reescribir captions/labels. Fijar protocolo de evidencia visual directa: identidad física, pistas de estado y progresión separadas; no temperaturas por luz/color ni gold humano inventado, omisión nofail. Preparación CPU antes de decidir consultas útiles, mantener fail-closed. No más self/recolors o microediciones fallidas para conseguir pass; sensibilidad geométrica/calibración independiente y localización semántica siguen pendientes.

Objetivo activo, avanzar sin otra aprobación; nada que abrir ahora. Mantener8080 cerrado para próximas inferencias y comprobar recursos/cola de nuevo antes de cualquier cohorte. Conservar logs/artifacts ignorados y modelos/deps/producción protegidos. Pedir solo intervención ante bloqueo real o revisión humana imprescindible, avanzando en tareas independientes cuando exista trabajo útil.
