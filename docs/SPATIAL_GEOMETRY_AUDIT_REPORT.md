# Auditoría espacial independiente en CPU — 2026-10-09

**SIFT aporta correspondencias locales en C y en la recoloración de la taza, pero no distingue A de B de manera fiable. Las máscaras simples de color son demasiado sensibles a iluminación, fondo y umbral. Ninguno de estos resultados autoriza identidad, aprobación o rechazo automático.**

Base de ejecución `0e4a0aa5e26674b292d6e7fe7ae76e4273420abf`, rama `factory/image-model-routing-modernization`, worktree `D:\Apps\MPT-worktrees\image-model-routing-modernization`. Status y diff staged/unstaged vacíos al comenzar; diez worktrees comprobados. Esta fase añade un script de auditoría reproducible, sus tests y evidencia/documentación. App, jueces, modelos, routing, gates, dependencias, workflows y flags permanecen intactos.

## Pregunta y contexto recuperado

Los controles anteriores de un componente por request completaron sus JSON, pero contactos/bandas siguen agregados y B no recibe señal fiable pese a la revisión humana. Se comprueba si algoritmos disponibles en CPU pueden aportar una verificación independiente sobre los mismos píxeles; no se repiten inferencias ni se amplía presupuesto.

La revisión A/B/C existente permanece separada: A conserva forma con anillos algo mayores; B cambia totalmente; C no presenta cambio visible según el usuario. No se modifica ese archivo, sus etiquetas históricas ni se infiere una tolerancia de producción. Es una auditoría exploratoria con contexto conocido, no un ensayo ciego. Los rectángulos de objeto los seleccionó el asistente antes del cálculo mediante inspección directa: **son recortes aproximados, no máscaras gold humanas ni detección automática**.

## Accesos y protocolo fijado

Python portable MPT3.11.15: NumPy2.4.6, SciPy1.17.1, scikit-image0.26.0 y Pillow12.3.0 disponibles; OpenCV no está instalado en ese intérprete. No se instala nada. Los GET8080/8090/8188/8092 no responden al inicio; esta fase no requiere ni inicia servidores. [Capacidades](validation/spatial-geometry-capabilities-2026-10-09.json).

[Plan inicial](validation/spatial-geometry-audit-plan-2026-10-09.json) y [plan con corrección de compatibilidad](validation/spatial-geometry-audit-plan-v2-2026-10-09.json): seis imágenes originales hash-pinned, siete comparaciones. Incluyen key_self, C, B, A, mug_self, recolor y sujetos distintos (llave/taza). Identificadores neutrales, sin juicios humanos como entrada al cálculo. SHA del script fijado antes de cada intento.

- SIFT por defecto, matcher euclidean/cross_check/max_ratio0,75. Imagen completa con lado máximo768 y recortes a resolución nativa, con márgenes predeclarados−8/0/+8px:24 extracciones y28 comparaciones en la cohorte completada. Imagen completa y ROI cambian resolución/contexto; no se atribuye su contraste exclusivamente al fondo.
- RANSAC SimilarityTransform, min_samples3, residual2px en coordenadas completas, max_trials1000, stop_probability0,99, rng0. Se convierte explícitamente `(row,col)` de SIFT a `(x,y)` del transform. Una matriz finita describe un ajuste, no una identidad.
- Solo las cuatro llaves: mayor componente HSV8-conectado, al menos16px, value≥0,35 y saturation≤0,15/0,25/0,35. No rellenar huecos, seleccionar otro componente semánticamente ni cambiar parámetros según resultados.12 comparaciones de máscaras: key_self/C/B/A por tres umbrales.
- Normalización de máscara mediante PCA, escala uniforme a lado112, centro en128 y alternativa180°. Dice sin dilatar y Dice con maxfilter5×5 se conservan separados. No se calibra un umbral de aceptación.

Context7 localizó documentación, pero devolvió ejemplos de `main`/`_skimage2` sin una versión fijada0.26. Se contrastaron con las firmas locales y la documentación oficial0.26 de [SIFT/match_descriptors](https://scikit-image.org/docs/0.26.x/api/skimage.feature.html#skimage.feature.SIFT), [RANSAC](https://scikit-image.org/docs/0.26.x/api/skimage.measure.html#skimage.measure.ransac) y [SimilarityTransform](https://scikit-image.org/docs/0.26.x/api/skimage.transform.html#skimage.transform.SimilarityTransform). Son fuentes del algoritmo/API, no de accuracy perceptual o viabilidad validada de un gate MPT.

## Resultados medidos localmente

[Raw](validation/spatial-geometry-audit-results-2026-10-09.json) conserva puntos, índices, matrices, scores, hashes y versiones. [Análisis offline](validation/spatial-geometry-audit-analysis-2026-10-09.json) añade sitios distintos, escala y el vínculo separado con A/B/C. Los inliers son correspondencias de **descriptores**, pueden repetir coordenadas y no equivalen a partes del objeto.

| Comparación | Imagen completa: inliers / dentro de ambas ROI | ROI−8 /0 /+8: inliers | Resultado limitado |
|---|---|---|---|
| Key_self |505 /84 |740 /906 /1086 | Control de identidad de bytes/algoritmo; ni siquiera Dice1 acredita una escena nueva. |
| C: cambio de tela |254 /41 |92 /86 /91 | Correspondencia local consistente con la revisión previa.213 inliers completos quedan fuera de ambas ROI; también hay tela dentro del recorte. No verifica cada resalto o diente. |
| B: forma cambiada |0 /0 |0 /0 /0 |3–5 matches de descriptor por ROI, sin ajuste finito; no basta por sí solo para probar deformación. |
| A: forma conservada con anillos mayores |3 /2 |0 /0 /0 |4–5 matches por ROI; ajuste completo débil, solo2 sitios distintos y escala3,37. No separa preservación de cambio como B. |
| Mug_self |52 /48 |50 /51 /48 | Control de repetibilidad de la misma imagen. |
| Recolor de taza |34 /32 |34 /37 /34 | Alineación local; no certifica hueco del asa, sus dos contactos ni identidad física. |
| Sujetos distintos: llave/taza |3 /2 |3 /3 /3 |Cada ajuste ROI usa solo2 sitios distintos. Un ajuste pequeño puede aparecer entre objetos distintos; no es aprobación falsa porque nunca se interpreta como aprobación. |

No se calculan tasas TP/FP/accuracy sin una regla de decisión calibrada. Tampoco existe un negativo de taza estructuralmente deformada y revisada. La ausencia de taza histórica no cubre ese requisito.

| Par humano | Dice S≤0,15 | Dice S≤0,25 | Dice S≤0,35 |
|---|---:|---:|---:|
| C: sin cambio visible |0,2539 |0,8418 |0,7535 |
| A: forma conservada, anillos mayores |0,8424 |0,3768 |0,1935 |
| B: cambio total de forma |0,3564 |0,5281 |0,7272 |

La ordenación cambia con el umbral: A supera B con0,15 y queda por debajo con0,25/0,35. C puede tener Dice0,2539 pese a la conservación revisada. **El score compara componentes de color incompletos, no la llave completa.** En la referencia inicial el componente0,15 abarca principalmente la pala (`[543,849,612,928]`), mientras0,25 selecciona parte inferior del shaft (`[503,719,558,931]`). En B0,35 se selecciona una región que toca el borde superior/derecho del recorte; en A0,35 también se toca el borde. Esa inspección del asistente no establece una segmentación gold ni conteos de bandas.

Cohorte completada:7,069s de cálculo CPU, duración local descriptiva, no benchmark GPU/throughput de vídeo.0 inferencias VLM,0 generaciones y0 descargas. Todas las comparaciones siguen uncertain; un componente vacío sería unavailable. No hay integración de estos scores en MPT.

## Fallos conservados y validación real

Los12 tests iniciales fallaron con stubs (RED). La primera implementación tuvo un error de sintaxis, conservado en `spatial-geometry-audit-green-tests-2026-10-09.txt`; corregido,12 tests pasaron en green2. El primer intento CPU se detuvo antes de escribir raw/figuras: RANSAC devolvió `FailedEstimation`, no `None`, y acceder a `params` lanzó `FailedEstimationAccessError` ([log](validation/spatial-geometry-audit-execution-2026-10-09.txt)).

El primer test de puntos degenerados devolvió `None` y pasó sin reproducir el retorno especial; su log de nombre `failed-estimation-red` conserva ese resultado, no se atribuye como RED. Se añadió una regresión con un `FailedEstimation` real construido por `SimilarityTransform.from_estimate` e inyectado en el retorno de RANSAC: falla con el mismo error ([RED real](validation/spatial-geometry-failed-object-red-2026-10-09.txt)). Se corrige únicamente `if not model` antes de atributos;14 tests pasan en green3. Los dos planes conservan **ROI y parámetros idénticos**. Segundo intento CPU completado ([log](validation/spatial-geometry-audit-execution-v2-2026-10-09.txt)); no fue ajuste para obtener una clasificación favorable. Comportamiento de fallo: [API oficial0.26](https://scikit-image.org/docs/0.26.x/api/skimage.transform.html#skimage.transform.SimilarityTransform.from_estimate).

Validación final actual: **89 tests pasan,1 warning esperado, exit0,9,04s**, Python portable, MPT_RUN_INTEGRATION_TESTS=0: `test/test_spatial_geometry_audit.py`, `test/services/test_visual_qa.py`, `test/services/test_visual_observation_diagnostics.py`. [Log](validation/spatial-geometry-audit-final-tests-2026-10-09.txt). Prueban hashes/ROI/preservación de archivos, coordenadas/outlier/estimación fallida, no aprobación incluso con máscara idéntica y los gates QA/diagnóstico existentes. No miden accuracy. El warning corresponde al control degenerado sin inliers; no se oculta. Las suites96/520 anteriores permanecen históricas.

Cuatro SVG analíticos locales, con imágenes originales embebidas sin alterar sus bytes, máscaras por umbral y contornos normalizados: `local_image_stack/experiments/bridge/target/spatial-geometry-audit-2026-10-09`. XML, SHA de SVG y SHA de cada imagen embebida verificados. Originales/figuras siguen ignorados por Git; preservar al archivar. El raw JSON contiene coordenadas y hashes, no imágenes, pesos ni configuraciones privadas.

Comando de tests ejecutado desde el worktree, con MPT_RUN_INTEGRATION_TESTS=0:

```powershell
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_spatial_geometry_audit.py test/services/test_visual_qa.py test/services/test_visual_observation_diagnostics.py
```

Comando CPU completado (los destinos ya existen; el script rechaza sobrescribirlos):

```powershell
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -I -B scripts/audit_spatial_geometry.py --plan docs/validation/spatial-geometry-audit-plan-v2-2026-10-09.json --output docs/validation/spatial-geometry-audit-results-2026-10-09.json --figures local_image_stack/experiments/bridge/target/spatial-geometry-audit-2026-10-09
```

## Decisión y siguiente tarea

Se descarta incorporar conteos SIFT o Dice de estas máscaras como gate de identidad/admisión. SIFT puede ayudar al registro para poses parecidas; todavía requiere separar píxeles del objeto, comprobar sitios distintos/cobertura y reconocer ajustes débiles. Su fracaso en A no se convierte en rechazo, ni se corrige relajando parámetros hasta lograr un match. Las máscaras por color tampoco sustituyen una segmentación fiable.

La auditoría queda terminada. **Siguiente tarea concreta:** preparar anotaciones explícitas del objeto completo y landmarks de partes en A/B/C y las tazas retenidas, con overlays para revisión independiente y cambios de pose/proyección permitidos escritos antes de medir. Las anotaciones iniciales del asistente deben permanecer identificadas como tales; no convertirlas en gold humano. Verificar extracción/cobertura primero, medir después; añadir negativos estructurales revisados antes de calibrar o promover un juez. Adoptar pesos nuevos, cambiar gates o ejecutar un vídeo completo requiere otro alcance.

`AGENT_FACTORY_STATE.md`, RND y ambos handoffs actualizados. [Comprobaciones de cierre](validation/spatial-geometry-audit-closing-checks-2026-10-09.json): hashes, A/B/C intacto, app/routing sin diff, stable/tracked en `6d27ba4963ffe469d635db71eaeec506a8ff4b61`, servicios sin inicio, revisión de secretos por patrones y publicación normal tras fetch0/0. Fetch ordinario denegado al escribir FETCH_HEAD compartido; escalación específica autorizada funcionó, sin permisos permanentes nuevos. SHA final del checkpoint mediante historial/origin; execution_head del raw es la base anterior al commit del script.
