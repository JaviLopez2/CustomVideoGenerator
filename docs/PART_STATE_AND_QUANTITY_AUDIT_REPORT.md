# Contratos de partes, estado y recuento — 2026-10-10

La auditoría encuentra una frontera de contrato pendiente y corrige un fallo léxico de recuento: una mención numérica negada podía producir `pass`. **384 pruebas CPU pasan; los 34 checks de cantidad archivados conservan exactamente su resultado.** Esto no mejora por sí solo la percepción de los jueces ni aprueba ninguno para producción.

Base: `f39b46d3544243f563615e408fe26cc70b935b04`, rama `factory/image-model-routing-modernization`, worktree Windows habitual. Inicio limpio y diez worktrees comprobados. La revisión humana de relojes ya estaba registrada: agujas/llaves 2/1, 3/1, 2/2, 3/1. La llave 3 presenta formas convergentes en un cabezal; no son dos objetos separados certificados. La preferencia estética por 4 no acredita identidad. Se conserva el [literal previo](validation/clock-visible-count-human-review-2026-10-10.json) sin duplicar muestras o solicitar de nuevo esa valoración.

## Frontera de contrato

- `material._download_videos_openai_image_on_demand` acepta `scene_qa_contracts`; el wrapper público `download_videos` no expone ese campo. La rama experimental se activa únicamente con contratos explícitos y `openai_image_visual_qa_experimental_enabled is True`. En la configuración leída durante esta auditoría esa condición es falsa; no se modifica la configuración.
- El constructor actual es `FlorenceEvidence`. Las consultas diagnósticas anteriores a Qwen3.5/Qwen3-VL no han sustituido el motor de QA de MPT.
- `allowed_changes` solo permite rotación en la comparación de silueta exterior. No expresa qué partes del sujeto deben conservarse frente a salidas o estados funcionales. La coincidencia de máscara exterior no acredita partes internas, uniones o identidad; los guardas siguen absteniéndose.
- El callback pareado es privado, explícitamente inyectado y sin autoridad de admisión. Su consulta genérica de partes no lleva contexto de cambios funcionales permitidos. No cambiar la categoría archivada ni introducir una excepción por la palabra «paper» para resolver el desacuerdo de cámara.
- El requisito de referencia por defecto es `identity`, también si un test omite esa metadata en una ruta estándar. Un contrato de solo cantidad no satisface ese requisito. El rechazo del primer control positivo de la nueva prueba era correcto: el fixture debía declarar `scene_reference_needs=["none"]` para aislar el recuento. Los gates del producto permanecen intactos.

[Auditoría reproducible y bindings](validation/part-state-and-quantity-audit-2026-10-10.json), [recipe CPU congelado](validation/part-state-and-quantity-audit-recipe-2026-10-10.py). El recipe liga código, pruebas, documentos de cámara y archivos históricos por SHA; comprueba los argumentos mediante AST y conserva `state_check`, `silhouette` y `overall` sin cambios. Se ejecutó con Python MPT `-I -B`, sin cargar Florence ni hacer HTTP. Rechaza inputs cambiados o una salida existente.

El desacuerdo de cámara sigue siendo Qwen3.5 `not_observed` frente a Qwen3-VL `observed`, con distinta interpretación de la fotografía que sale. No establece un defecto en el cuerpo ni un negativo geométrico independiente. Su [tablero de revisión](validation/camera-independent-review-preparation-2026-10-10.json) oculta los valores de los modelos, pero el chat ya describió el desacuerdo: no se acredita una revisión humana completamente ciega. La valoración de cámara sigue pendiente y no bloquea trabajo CPU independiente. No se repiten las consultas de esa cohorte cerrada para obtener otro resultado.

## Causa y corrección de recuento

V4 extraía el número mencionado sin comprobar su afirmación. Por ejemplo, `Not a single key is visible.`, `Two keys have not been seen.` o `There are two absent keys.` podían certificar 1 o 2. Son controles sintéticos de lenguaje, no fallos perceptuales medidos sobre imágenes.

V5 conserva `caption_counts` como conjunto de menciones léxicas y examina cada mención en `quantity`: negación anterior con proximidad acotada, ausencia/negación posterior de visibilidad y modificadores `absent`/`missing` dentro de la mención. Admite contracciones, apóstrofo tipográfico y auxiliares de esos mismos predicados. Devuelve `uncertain` con `observed_count=None`, sin inventar un recuento alternativo aunque OD repita el número negado. Se conservan cláusulas de otros sujetos y propiedades como `Two keys have not been painted blue.`; dobles negaciones y límites «no more/fewer than» se abstienen. `VERSION=visual-qa-5` impide reutilizar el antiguo pass de caché, sin borrar registros previos ni cambiar la caché de extracción visual.

La revisión independiente encontró dos P2: auxiliares postfix y ausencia dentro de los adjetivos. Se reprodujeron en ocho RED antes de corregirlos, con controles afirmativos y aliases. No se expande aquí a gramática general: negación partitiva, predicados nuevos o ausencia de sujetos coordinados permanecen fuera de la cobertura demostrada. Un parser léxico no certifica la verdad del caption ni resuelve oclusiones, fusión o identidad.

## Evidencia y pruebas

45 nuevos casos del parser/caché y 2 casos del loop MPT con QA real sobre captions y OD simulados; generación, render y servicios sustituidos. Ambos casos aíslan explícitamente una escena sin requisito de referencia: el afirmativo se admite y el negado se rechaza; una sola generación simulada, dos lecturas de evidencia y cero QA gross. No es una prueba end-to-end de servicios reales.

- [RED inicial](validation/quantity-negation-red-tests-2026-10-10.txt): 19 failed / 10 passed, 1,23 s, exit 1.
- [GREEN inicial](validation/quantity-negation-green-tests-2026-10-10.txt): 135 passed, 3,46 s, exit 0.
- [RED de modificadores](validation/quantity-negation-modifier-red-tests-2026-10-10.txt): 4 failed / 18 passed / 11 deselected, 0,24 s, exit 1.
- [Primer run amplio](validation/quantity-negation-final-tests-2026-10-10.txt): 1 failed / 297 passed, 20,34 s, exit 1. Se conserva el error del fixture de identidad explicado arriba; no es un cierre verde.
- [RED de revisión](validation/quantity-negation-review-red-tests-2026-10-10.txt): 8 failed / 37 passed, 0,30 s, exit 1.
- [GREEN de revisión](validation/quantity-negation-review-green-tests-2026-10-10.txt): 86 passed, 3,21 s, exit 0.
- **[Final v2](validation/quantity-negation-final-v2-tests-2026-10-10.txt): 384 passed, 22,04 s, exit 0, sin avisos.**

Comando final con Python MPT, `MPT_RUN_INTEGRATION_TESTS=0`, offline HF/Transformers y `PYTHONIOENCODING=utf-8` solo en el proceso:

```text
-B -m pytest -q test/services/test_visual_qa_quantity_negation.py test/services/test_visual_qa.py test/services/test_visual_qa_state_evidence.py test/services/test_visual_qa_state_negation.py test/services/test_material_paired_diagnostics.py test/services/test_paired_visual_observation_diagnostics.py test/services/test_corrective_continuity.py test/services/test_klein4b_mpt.py test/services/test_evidence_pruning_root_qa.py --tb=short
```

Replay de 16 filas / 34 checks de cantidad: captions y OD históricos exactos, SHA de cada candidato y observación comprobados; V4 y V5 devuelven resultados idénticos. No se reextrae evidencia ni se ejecuta el QA visual completo. Los labels históricos del asistente no se convierten en gold humano; no hay nueva precisión o latencia de inferencia medida. El primer intento de registrar la auditoría falló por lectura de texto cp1252 de Windows antes de escribir su salida; el recipe final usa UTF-8 explícito.

0 nuevas inferencias, generaciones, descargas, jobs, controles de servicios o benchmarks GPU. Solo cambia el parser de cantidad y su versión de caché en el código experimental; no se activan flags, modelos, routing o workflows, ni se modifican dependencias o MPT estable. [Checks de cierre](validation/quantity-negation-closing-checks-2026-10-10.json); SHA de entrega verificable en Git/origin.

## Siguiente tarea

Preparar en CPU un contrato genérico que separe partes estructurales del sujeto y cambios de estado permitidos, ligado a los contratos reales de escena. Inventariar controles retenidos con procedencia y etiquetas suficientes, incluyendo fusión y otra familia; declarar como pendientes los negativos desconocidos y la revisión de cámara. Fijar la metodología antes de otra consulta y preservar cohortes cerradas. Después siguen calibración de error/abstención y latencia del QA completo; Qwen3.5 es preferente únicamente en los recuentos de los cuatro relojes, sin selección general o promoción. El objetivo autónomo sigue activo y esta preparación no requiere servidores ni otra aprobación rutinaria.
