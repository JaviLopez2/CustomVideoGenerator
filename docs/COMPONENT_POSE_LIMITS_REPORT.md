# Límites de componentes y perspectiva — 2026-10-09

**La comparación de forma necesita separar perspectiva, profundidad y error de anotación.** Se completaron 33 controles sintéticos en CPU y 66 ajustes, con correspondencias conocidas por construcción. Una homografía puede encajar cuatro puntos deformados y seguir sin verificar ninguna otra parte. Estos controles no estiman la pose de las fotos de MPT, no alteran el juicio humano sobre B y no permiten elegir todavía un juez de identidad.

Base publicada `19c660b9aff0e5b7f17159c4701ce91838df920e`, rama `factory/image-model-routing-modernization`, worktree experimental Windows. Carpeta, rama, HEAD, status, ambos diffs y diez worktrees comprobados; inicio limpio. Reutilización del worktree y de las seis imágenes originales. [Plan fijado antes de ejecutar](validation/component-pose-plan-2026-10-09.json), con hashes de script, anotación v3 y ambas revisiones humanas. El checkpoint posterior se identifica en Git/origin; `execution_head` permanece en la base.

## Auditoría de componentes reales: metadatos, sin scores

Los puntos amarillos parecían coincidir según el usuario, pero esa revisión local no certifica correspondencias físicas entre imágenes. Se verificaron los seis SHA originales y los datos/revisiones existentes. No se ajustó ninguna transformación ni se calcularon distancias, ratios o scores sobre las fotos.

| Par retenido | Nombres de puntos compartidos | Límite |
|---|---:|---|
| Referencia → C | 6 | Mismos nombres no demuestran correspondencia ni exactitud de cada parte. |
| Referencia → A | 5 | Las esquinas anotadas de la hoja no tienen el mismo conjunto de roles. |
| Referencia → B | 0 | B tiene sitios de punta, conexión, collar y abertura distintos; no se emparejan por orden ni mediante sinónimos inventados. Máscara completa discutida y excluida. |
| Taza roja → azul | 6 | Posiciones aproximadamente revisadas; no identidad física certificada. |

Los roles no compartidos describen diferencias de anotación, no piezas físicas ausentes. Los juicios A/B/C y las dos respuestas humanas se conservan intactos. B sigue siendo el caso de cambio total de forma según el usuario; los experimentos sintéticos no reinterpretan ese juicio como un cambio de cámara.

## Protocolo sintético y fuentes

Modelo matemático pequeño de ocho puntos: cuatro esquinas planas para ajustar, cuatro puntos distintos para comprobar. Dos variantes, todos coplanares y dos puntos internos a profundidades +0,8/−0,6 unidades. Cámara pinhole ideal, focal600px, centro(320,240), distancia6 unidades, rotación `Ry @ Rx`, sin distorsión u oclusión. Grid predeclarado Rx0/15/30° y Ry0/15/30/45/60°: 30 proyecciones de geometría rígida intacta. Se añaden rotación en plano37°/escala1,3/traslación(10,−20), desplazamiento de un punto de comprobación12px y deformación de una esquina(25,−10) con solo cuatro puntos disponibles.

Similarity y Projective se estiman sin pesos ni RANSAC, con los mismos cuatro anclajes y puntos de comprobación separados. La homografía se usa como control de limitaciones, no como normalización autorizada de identidad. Se conservan todas las coordenadas, matrices y residuos; no se buscan parámetros o umbrales que hagan pasar casos.

La [documentación oficial OpenCV4.13.0](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html) relaciona homografía con geometría planar y describe la proyección pinhole y los datos requeridos para recuperar pose. Se usa como fuente matemática; OpenCV no está instalado ni se incorpora al proyecto. Una foto generada no acredita por sí misma un objeto rígido, un plano o una cámara calibrada.

Context7 devolvió ejemplos de `main`/`_skimage2`; se contrastaron con las firmas locales y la [API oficial scikit-image0.26.0](https://scikit-image.org/docs/0.26.x/api/skimage.transform.html). Se usa `from_estimate` y se comprueba `bool(model)` antes de acceder a parámetros, preservando estimaciones fallidas como unavailable. NumPy2.4.6, scikit-image0.26.0 y Pillow12.3.0 ya existentes; ninguna dependencia nueva.

## Resultados medidos localmente sobre los controles sintéticos

[Raw completo](validation/component-pose-results-2026-10-09.json). Unidades de los residuos: píxeles de la cámara matemática declarada, no píxeles de las fotos de MPT. Valores cercanos a 1e−13 representan precisión numérica, no precisión perceptual.

| Control | Similitud: máximo en puntos de comprobación | Homografía: máximo en puntos de comprobación | Resultado |
|---|---:|---:|---|
| Rotación en plano y escala uniforme | ≈0 | ≈0 | La normalización restringida funciona en este caso construido. |
| Plano intacto, Ry45°/Rx0° | 12,890px | ≈0 | Cambio de vista puede producir discrepancia sin deformación. |
| Partes a distinta profundidad, Ry45°/Rx0° | 48,680px | 54,137px | La homografía del plano no corrige todas las partes 3D. |
| Parte no usada para ajustar desplazada12px | 12px | 12px | Encaje exacto de anclajes no oculta el cambio si existen comprobaciones independientes. |
| Cuatro esquinas, una deformada | Sin puntos de comprobación | Sin puntos de comprobación | Homografía encaja los anclajes con máximo1,45e−13px; eso no valida la forma. |

Máximo de todo el grid: plano intacto18,752px con similitud y ≈0 con homografía; variante con profundidad59,314/71,208px respectivamente. No son tolerancias de aceptación ni errores esperados de las llaves/tazas reales.

Control de incertidumbre: suponiendo cada punto dentro de un disco de radio3px, separaciones nominales30/35px tienen cotas24–36/29–41px, que se solapan. Con longitud de referencia supuesta194–206px, los ratios también se solapan. Son cotas deterministas condicionadas a esos supuestos, no intervalos de confianza medidos ni una medición del tamaño de los anillos de A.

## Validación y preservación

Herramienta aislada `scripts/probe_component_pose_limits.py`, sin imports o conexión de app/QA/routing. 19 pruebas nuevas: proyección conocida, entradas inválidas, controles de perspectiva/profundidad/deformación, anclajes y puntos de comprobación disjuntos, geometría collinear, cotas de incertidumbre, procedencia y preservación de outputs. RED19 fallos del esqueleto; GREEN19 aprobadas; [logs](validation/component-pose-green-tests-2026-10-09.txt) conservados.

```powershell
$env:MPT_RUN_INTEGRATION_TESTS = '0'
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_component_pose_limits.py test/test_spatial_annotation_review.py test/test_spatial_geometry_audit.py test/services/test_visual_qa.py test/services/test_visual_observation_diagnostics.py
```

**124 passed, 1 warning, 8,86s, Python exit0** en la ejecución actual. Aviso esperado del control de RANSAC degenerado anterior. [Log](validation/component-pose-final-tests-2026-10-09.txt), [comprobaciones de cierre](validation/component-pose-closing-checks-2026-10-09.json). Los 105 anteriores son históricos y no se presentan como una nueva prueba separada de esta ejecución.

Diagrama SVG reproducible y PNG revisado visualmente en `target/component-pose-limits-2026-10-09`, ignorados por Git; conservar al archivar junto a fotos/borradores y runtime previo. Render con Node/sharp existente, exit0, sin navegador ni servidor; las restricciones de caché Fontconfig no impidieron el render y no se alteraron permisos globales. [Diagrama local](D:/Apps/MPT-worktrees/image-model-routing-modernization/local_image_stack/experiments/bridge/target/component-pose-limits-2026-10-09/synthetic-controls.png).

App, modelos, gates, flags, dependencias, routing, workflows, anotaciones y auditorías previas intactos. 0 comparaciones de identidad reales, inferencias VLM, generaciones, descargas, benchmarks GPU o servicios iniciados/parados. Stable sigue en6d27ba4 con status tracked vacío; untracked existentes preservados. Fetch0/0 antes de checkpoint, escalación específica para metadata Git, sin permisos permanentes.

## Decisión y siguiente tarea

La admisión automática basada en esta prueba permanece deshabilitada. Corregir perspectiva con un ajuste flexible no resuelve una comprobación de identidad; tampoco basta con comparar los mismos nombres de puntos. Se mantiene B fuera de métricas de máscara completa y no se añaden pesos o prompts de rescate.

Siguiente tarea concreta: contrastar las cajas VLM ya guardadas de hueco y contactos de las dos tazas con sus puntos aproximadamente revisados, por sitio y dentro de cada imagen, conservando margen±3px, regiones agrupadas y fallos originales. Usar los cuatro raw `isolated-mug-{hole,contacts}-{qwen35,qwen3vl}-2026-10-08.json`; no repetir inferencia ni estimar pose entre fotos. La cobertura puntual solo aportará localización diagnóstica, no segmentación exacta o identidad. No necesita servidores. Un negativo estructural de taza revisado y una regla calibrada de aceptación siguen pendientes antes de escoger/promover un juez.
