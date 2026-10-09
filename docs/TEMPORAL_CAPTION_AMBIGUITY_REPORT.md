# Evidencia temporal ambigua — parche experimental, 2026-10-09

El parser temporal deja de convertir menciones cualificadas o contradictorias en evidencia cierta. Tampoco acredita progresión desde un caption anterior ambiguo. Negativos inequívocos siguen fallando y la omisión sigue incierta. Esto corrige interpretación de texto; no demuestra que un caption sea visualmente fiel.

## Causa y alcance

Base `417dac34f5367c58412a0722f509ff3dbb2fbb39`, worktree/rama experimental, status y diffs inicialmente vacíos. [Auditoría previa](validation/temporal-caption-ambiguity-audit-2026-10-09.json), fuente `visual-qa-2`: `present()` acumula presencia/negación pero permite que presencia gane a la contradicción; no registra cualificación. Después `state_check()` interpreta un fail anterior como progresión aunque la ausencia fuera dudosa. Reproducido directamente en CPU, antes de editar.

| Texto / contrato | Antes | Después |
|---|---|---|
| «may have frost», requiere frost | pass, score1 | uncertain, score null |
| «has frost … has no frost», requiere frost | pass | uncertain |
| «might be smoke», prohíbe smoke | fail | uncertain |
| Actual frost; anterior «might have no frost» | progression1 | progression null; estado actual pass |

Se modifica solo `app/services/visual_qa.py` y se añade `test/services/test_visual_qa_state_evidence.py`. Vocabulario de estados proviene del contrato, sin reglas por objeto/escena. Cada término se evalúa una vez: presente, ausente, no mencionado o ambiguo. Cualificación modal, condicional o pregunta en la cláusula relevante y contradicción presencia/ausencia producen ambigüedad. El nuevo campo `ambiguous_evidence` explica los términos; no hay score concluyente de estado para uncertain ni identidad inferida. Una violación clara de otro requisito aún puede causar fail, pero cualquier ambigüedad anterior impide acreditar progresión.

Las cláusulas se separan por puntuación y conjunciones contrastivas explícitas; una duda sobre iluminación en otra cláusula no contamina automáticamente un estado afirmado. Los saltos de línea se conservan dentro de la frase: la revisión independiente detectó que separarlos rompía «no\nfrost» y «without\nsmoke». Cuatro regresiones reprodujeron el defecto antes de eliminar ese límite. La revisión posterior no encontró problemas en el diff acotado.

`VERSION` pasa de `visual-qa-2` a `visual-qa-3`. Las claves de caché existentes incorporan esa versión: un test siembra un pass v2 y verifica recomputación incierta en v3, sin añadir una nueva capa de caché. El cambio invalida también las entradas de evidencia versionadas; no borra archivos ni caches globales. Requisitos, modelos, flags/defaults, política de admisión y routing se conservan; no se activa la integración experimental.

## Pruebas reales

37 nuevos casos CPU, sin modelos/red/GPU. Cualificación antes/después del término, required/forbidden, contradicción y orden invertido, omisión, cláusulas independientes, captions multilínea, anterior ambiguo, progresión inequívoca, integración del `VisualQA` y cache v2.

- RED inicial:20 failed/13 passed,0,40s/exit1, [log](validation/temporal-caption-red-tests-2026-10-09.txt).
- GREEN inicial:72 passed,3,57s/exit0, [log](validation/temporal-caption-green-tests-2026-10-09.txt).
- Primera regresión amplia:182 passed,6,70s/exit0, anterior a la corrección de multilínea; [log conservado](validation/temporal-caption-final-tests-2026-10-09.txt).
- RED de revisión:4 failed/33 passed,0,32s/exit1, [log](validation/temporal-caption-review-red-tests-2026-10-09.txt).
- **Validación final:186 passed,6,55s/exit0/sin avisos**, [log](validation/temporal-caption-review-final-tests-2026-10-09.txt).37 nuevos y149 previos. Incluye QA, diagnóstico visual, integración Klein, continuidad correctiva y gates de evidencia/estado.

Comando final con Python MPT, `MPT_RUN_INTEGRATION_TESTS=0`: `-B -m pytest -q test/services/test_visual_qa_state_evidence.py test/services/test_visual_qa.py test/services/test_visual_observation_diagnostics.py test/services/test_klein4b_mpt.py test/services/test_corrective_continuity.py test/services/test_evidence_pruning_root_qa.py`. [Cierre y replay de cuatro reproducciones](validation/temporal-caption-closing-checks-2026-10-09.json). Los logs RED crudos conservan espacios de los diffs de pytest; se distinguen de checks de whitespace en fuente/documentación, sin alterar la evidencia.

Esta fase no envía consultas a modelos ni generación, no modifica servicios ni mide latencia GPU/VRAM o mejora end-to-end.0 descargas/dependencias/modelos/workflows activos/Factory/estable. Los12 requests y184 tests del [contraste de forma](PAIRED_SHAPE_PROBE_REPORT.md) pertenecen al checkpoint anterior y siguen separados; no se repiten ni se atribuyen a este cambio.

## Límites y continuación

Parser léxico de captions ingleses y vocabulario literal del contrato, no analizador universal de semántica, sujeto, alcance de negación o idiomas. Conserva el reconocimiento de negación próxima anterior del mecanismo existente; las negaciones posteriores, dobles o complejas no se afirman resueltas. Puede abstenerse ante una cualificación que afecta otra parte de la misma cláusula. Los scores de estado/progreso representan soporte en texto, no probabilidad visual calibrada. No convierte captions inventados en verdad ni certifica identidad.

Siguiente tarea CPU: contrastar captions temporales archivados y contratos reales con v2/v3, preservando el raw y diferenciando verdad humana de etiquetas del asistente; auditar negaciones explícitas restantes antes de ampliar consultas. Después queda la preparación reproducible de regiones y el contraste ROI con otra familia. Los casos A/B/C recortados son prometedores pero no permiten promover gates ni routing. La autonomía sigue activa; no se necesita abrir servicios o aprobar otro checkpoint.
