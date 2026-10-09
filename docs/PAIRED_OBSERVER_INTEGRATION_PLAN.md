# Observadores pareados: auditoría e integración diagnóstica — 2026-10-09

Desde `90ff646452c51200618e317829574b5ea0fb11ce`, worktree/rama experimental, inicio limpio y diez worktrees. La auditoría confirma un punto de diagnóstico existente, pero su store de una imagen no representa los nuevos pares. Se prepara una extensión de replay offline; **no se conecta un juez al gate ni se modifica la aplicación en esta fase**.

## Qué existe y qué falta

| Requisito | Implementación actual inspeccionada | Límite para los pares |
|---|---|---|
| Selectividad | `VisualQA.assess` omite visión sin requisitos y corta checks después de fail | Ya existe; no añadir otra cascada obligatoria |
| Caché | `EvidenceCache`, hashes de candidato/referencia/anterior, contrato, versión QA y modelo | Cachear un par exige además orden, consulta y preparación; no reutilizar por candidato solo |
| Cantidad | `quantity` combina caption/OD y conserva conflicto/ambigüedad | Los observadores pareados no cuentan objetos; no pueden sustituirlo |
| Geometría | Silueta externa normalizada, bandas preliminares; estructura interna no acreditada queda uncertain | `major_shape_change` es observación cualitativa, no score calibrado o prueba de identidad |
| Estado | Parser temporal v4 distingue ausencia explícita, omisión y ambigüedad | Una cue visual no resuelve todas las cláusulas required/forbidden o still liquid |
| Identidad crítica | Check explícito uncertain con identity_score null | No se satisface con reconocimiento, mismo color o ausencia de gran cambio |
| Admisión experimental | Requiere QA explícitamente pass; incertidumbre/unavailable eliminan candidato | Un diagnóstico pareado nunca rehabilita ese candidato |

Punto privado: `material._download_videos_openai_image_on_demand`, parámetros `scene_qa_contracts` y `visual_observation_store`, línea7241 en esta base. El replay actual se adjunta antes de QA en `source_info.visual_observation_diagnostic` y en los diagnósticos del run. No se usa para selección, retries o admisión. Su lectura es opt-in mediante store inyectado, sin modelo, endpoint, UI o flag persistido nuevo. El QA conjunto requiere además contrato explícito y boolean `openai_image_visual_qa_experimental_enabled=True`; si corre, evita duplicar gross/temporal. No lo sustituir por el replay: su verdict uncertain descartaría escenas en vez de observarlas pasivamente.

`RetainedVisualObservations` —último cambio3e2b873— acepta cuatro protocolos de inventario de una imagen y busca solo el SHA del candidato. No acepta `paired-major-shape-observations-1` ni `pairwise-visible-cue-observations-1`. La comprobación CPU intenta cargar ambos nuevos raw de cues y reproduce rechazo `Unsupported observation protocol`; es incompatibilidad de interfaz prevista, no fallo de HTTP/modelo. No corregirla cambiando el nombre de protocolo o fingiendo un inventario de una imagen.

## Correspondencia de archivos y contexto

[Plan CPU fijado](validation/paired-observer-integration-audit-plan-2026-10-09.json), doce archivos de código/tests y ocho inputs retenidos ligados por SHA. [Receta](validation/paired-observer-integration-audit-recipe-2026-10-09.py), [resultado](validation/paired-observer-integration-audit-result-2026-10-09.json), [log](validation/paired-observer-integration-audit-execution-2026-10-09.txt): exit0, sin llamadas a modelos/servicios. Reutiliza el preflight de cues para reconstruir cuatro fotogramas completos nativos, con flags de gold/identidad/admisión false.

Dos fotogramas512 tienen distinto SHA de archivo al quitar metadata, aunque píxeles/modo/dimensiones sean exactos; los otros dos768×1376 mantienen también los bytes. No buscar las observaciones usando un SHA preparado como si fuera el original, ni relajar la comparación por similitud. Hace falta un vínculo source→prepared verificado por plan/manifiesto/helper, con rectángulo y dimensiones. Los ROI de forma tienen además cajas/margen explícitos; cobertura rectangular no equivale a localización semántica automática o verdad de sus partes. Fotograma completo de cues y ROI de forma no son inputs intercambiables.

Referencia→candidato de forma y anterior→actual de cue son roles distintos. Mismo candidato con otro anterior, otra referencia, orden invertido, sujeto o consulta no corresponde a la misma observación. Datos fuera de esa correspondencia se muestran sin observación disponible; no sintetizar respuestas para los casos no ejecutados. Las observaciones se ligan a la etapa anterior al QA: una transformación posterior de píxeles invalida su uso como evidencia de la imagen final, incluso si conserva ruta/nombre.

Control CPU adicional: `VisualQA` con contrato vacío devuelve pass/not_required sin cargar visión, pero `qa_verified` no lo acepta. El diagnóstico válido archivado de aparición tampoco lo satisface. El raw inválido Qwen3-VL sigue rechazado por presencia uncertain con cue not_observed. El último raw válido Qwen3.5 conserva la contradicción semántica potencial de describir oscuridad y declarar ausencia observada; no se normaliza por texto ni se cambia gold después.

## Primera implementación propuesta

[Diseño congelado](validation/retained-paired-replay-design-2026-10-09.json). Nuevo adaptador experimental offline en `scripts`, reutilizando los parsers/diagnósticos/preflight pareados ya existentes. Mantener el store de una imagen y la aplicación intactos en esta primera entrega. No duplicar validators dentro de MPT ni importar scripts experimentales desde sus módulos de producción.

1. Recibir bindings explícitos del raw y su plan ejecutado, raíz del worktree y contexto solicitado. Admitir inicialmente los dos raw de cue y los dos raw neutrales de forma cross-family conservados; ningún endpoint o resolución automática de modelo.
2. Verificar protocolo, plan/code bindings, sources/prepared y roles. Reconstruir payload conocido para cotejar su fingerprint; comprobar modelo/procedencia del raw y contenido final sin confiar en summaries/verdicts/gold del archivo. Usar los parsers estrictos existentes, con finish_reason/reasoning y coherencia de categorías. No seguir paths arbitrarios declarados por filas.
3. Guardar snapshot aislado por protocolo/modelo/plan/report/roles/source-prepared hashes/sujeto/consulta. Revalidar fuentes/preparación al consultar; cambios de fuente después de cargar no mantienen availability. Mismatch de contexto o par no grabado devuelve unavailable sin HTTP y conserva la causa.
4. Conservar raw y fallos. Una fila inválida/no completada permanece unavailable; una observación válida produce únicamente diagnóstico uncertain, tres scores separados null y admisión/rechazo/identidad física false. No convertir not_observed en ausencia global ni claimed shape match en identidad.
5. Exportar resultados inspectables bajo opt-in explícito, sin sobrescribir artifacts. Este paso no se adjunta a `scoped_qa`, no cambia QA/selección/retries/defaults y no introduce servicio residente. El siguiente puente al punto privado necesita su propia implementación y pruebas de no interferencia; primero cerrar el adaptador con replay CPU real.

Pruebas futuras del adaptador: protocolos y presupuesto acotados, SHA de raw/plan/code, raw inválido/truncado/reasoning/duplicados/tampered observation, roles/subject/query distintos, source o prepared cambiado antes/después de carga, ROI parcial/disjoint, binding legítimo alternativo que no corresponde al plan, raw snapshot/deep copies, ausencia de casos no ejecutados y nulidad de scores/admisión. Usar controles CPU y los cuatro reportes existentes; cero nuevas consultas/generaciones/descargas. No presenta esas pruebas como ya implementadas.

## Verificación actual y pendientes del objetivo completo

**142 tests existentes pasan en6,27s, exit0/sin avisos**: QA, estado/negación v4 y diagnóstico de una imagen. [Log](validation/paired-observer-integration-audit-tests-2026-10-09.txt). Cubren límites de contrato, falta de evidencia, caché, corto circuito, no duplicar QA, forzar identidad/temporal, fallo del diagnóstico y no interferencia en admisión; runtime/generación de esas pruebas simulados. No se añaden tests/código de la aplicación aquí, ni se repiten los182 del runner para atribuirlos a esta auditoría. Los doce bindings permanecen intactos.

Dataset original:16casos,9pass/6fail/1uncertain del asistente, sin nuevas etiquetas humanas independientes. A/B/C humano permanece separado. Los recuentos de labels no prueban precisión del juez. Siguen pendientes negativos geométricos válidos en otra familia, recuento/estado con revisión independiente, calibración de errores/abstención, cobertura semántica y latencia completa antes de escoger un juez y proponer routing. El resultado técnico de Klein y los hints nuevos no sustituyen esos requisitos.

Esta entrega cambia documentación/receta de auditoría exclusivamente; cero nueva inferencia, generación, descargas, servicios, modelos, dependencias, workflows, QA/routing/gates/defaults/estable. [Cierre](validation/paired-observer-integration-audit-closing-checks-2026-10-09.json). Próxima tarea autónoma: implementar/probar ese replay pareado offline; no requiere8080 ni intervención rutinaria. Objetivo completo todavía sin cumplir.
