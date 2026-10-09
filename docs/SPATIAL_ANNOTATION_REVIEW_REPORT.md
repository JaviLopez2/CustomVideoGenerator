# Contornos y componentes revisables — 2026-10-09

Se prepararon seis contornos completos, tres huecos y 36 puntos sobre imágenes retenidas. La revisión humana encontró errores reales en los contornos; se corrigieron B, los anillos de A y el borde izquierdo de ambas tazas. **B todavía incluye algo de sombra según la segunda revisión: su máscara completa queda excluida de mediciones de identidad y calibración. Ninguna anotación constituye verdad por píxel ni aprueba producción.**

Base de ejecución `03c36ba788090f8e904d5d7b49200e543cf98f8c`, rama `factory/image-model-routing-modernization`, worktree Windows habitual. Se conservaron los cambios de preparación que aún estaban sin commit y se revisaron status, ambos diffs y diez worktrees. Fetch posterior: 0/0 con origin. El SHA del checkpoint de cierre se identifica en Git/origin; no es el HEAD base registrado por las ejecuciones.

## Datos y procedencia

Se reutilizan las cuatro llaves y las dos tazas del [plan espacial previo](validation/spatial-geometry-audit-plan-v2-2026-10-09.json), con los mismos seis SHA y dimensiones. Las fotos originales se leen y se incrustan sin alterar sus bytes. Solo se dibujan diagramas derivados y se rasterizan máscaras nuevas. No se repiten la auditoría SIFT/HSV ni inferencias, generaciones o benchmarks.

Los polígonos y coordenadas los trazó el asistente sobre los píxeles originales: son estimaciones manuales. La máscara describe la apariencia visible proyectada, incluye el interior visible de la boca de las tazas y resta únicamente las aberturas de fondo declaradas. Se pretende excluir la sombra proyectada; la revisión demuestra que ese requisito sigue sin cumplirse plenamente en B. El margen de dibujo/borrosidad de 3–5 píxeles es una estimación, no un intervalo estadístico ni una tolerancia de identidad.

| Versión | Cambio y revisión |
|---|---|
| [v1](validation/spatial-annotation-draft-v1-2026-10-09.json) | Primer trazado: seis contornos, tres huecos, seis puntos por imagen. |
| [v2](validation/spatial-annotation-draft-v2-2026-10-09.json) | Inspección del asistente corrigió espesor visible de hojas y posiciones de dos puntos. El renderer con guardas adicionales produjo el archivo histórico llamado `review-final`; ese nombre no significa aprobación. |
| [Primera revisión humana](validation/spatial-annotation-human-review-2026-10-09.json) | B no coincidía; A demasiado estrecha en anillos; tazas excedían por la izquierda. Huecos de tazas aproximadamente coincidentes y puntos aparentemente correctos a la escala mostrada. |
| [v3](validation/spatial-annotation-draft-v3-2026-10-09.json) | Contornos de esas cuatro imágenes redibujados contra los originales; puntos, huecos y las dos primeras imágenes intactos. |
| [Segunda revisión humana](validation/spatial-annotation-human-review-v3-2026-10-09.json) | B aún toma algo de sombra y tiene una perspectiva difícil. Máscara de B discutida y excluida de identidad/calibración; la ausencia de comentarios sobre otros contornos no se convierte en aprobación explícita. |

Las respuestas humanas se conservan literalmente y se vinculan al SHA de la anotación y del tablero mostrado. El [juicio global A/B/C anterior](validation/visual-geometry-human-review-2026-10-08.json) no cambia ni se usa para ajustar scores. No se ha calculado ningún score de identidad en esta fase ni durante las correcciones.

## Herramienta y validación

`scripts/prepare_spatial_annotation_review.py` es una herramienta aislada, sin conexión a MPT/QA/routing. Comprueba límites enteros, polígonos no degenerados ni autointersectados, huecos interiores sin solapamiento, puntos dentro de la región declarada, SHA/tamaño de cada PNG y ausencia de sobrescritura de resultados. Rechaza que un borrador se declare revisado, verdad por píxel, elegible para métricas o correspondencia física certificada. Esas comprobaciones demuestran consistencia estructural; no detectan por sí mismas que una sombra se incluyó en el contorno.

La salida [v3](validation/spatial-annotation-review-v3-2026-10-09.json) conserva hashes de datos/script, máscaras y SVG, HEAD base y cero comparaciones/inferencias/generaciones. El render usa Pillow 12.3.0 ya instalado y Node/sharp del runtime incluido con Codex; no se instalan dependencias. Context7 localizó la documentación de [ImageDraw 12.3.0](https://github.com/python-pillow/pillow/blob/12.3.0/docs/reference/ImageDraw.rst): el polígono incluye sus píxeles de borde y se dibuja sobre una imagen de máscara nueva.

El visor rechazó `file://` por su política de URLs. No se intentó eludirlo con otro navegador o servidor: los controles del HTML generado siguen sin probarse en navegador. Se validaron y visualizaron los SVG/PNG estáticos. Fontconfig no pudo escribir su caché externa, pero se renderizaron los seis diagramas con exit 0; no se cambiaron permisos ni configuración global. El panel Codex devolvió `queued`, que no acredita apertura visible.

## Pruebas reales y preservación

TDD: primer esqueleto 14 fallos; implementación 14 aprobados. Dos regresiones adicionales fallaron antes de incorporar las guardas de revisión/correspondencia. Tras las correcciones v3 se ejecutó de nuevo:

```powershell
$env:MPT_RUN_INTEGRATION_TESTS = '0'
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_spatial_annotation_review.py test/test_spatial_geometry_audit.py test/services/test_visual_qa.py test/services/test_visual_observation_diagnostics.py
```

**105 passed, 1 warning, 6,06 s, Python exit 0**: 16 pruebas de anotación, 14 del auditor espacial y 75 de QA/diagnósticos. El warning esperado procede del control de RANSAC degenerado. [Log actual](validation/spatial-annotation-after-review-tests-2026-10-09.txt); los logs RED/GREEN y la ejecución anterior de 105 en 5,90 s se conservan separados. Los 89 de la fase anterior son históricos, no pruebas nuevas de este cambio.

[Comprobaciones iniciales](validation/spatial-annotation-artifact-checks-2026-10-09.json) y [cierre actualizado](validation/spatial-annotation-closing-checks-2026-10-09.json). Conservar al archivar los directorios ignorados `target/spatial-annotation-draft-2026-10-09`, `spatial-annotation-review-v1`, `review-v2`, `review-final` y `review-v3` con su sufijo de fecha, el snapshot inicial del renderer y todos los originales. Las fotos y artifacts de generación no se añaden al commit.

App, auditor espacial previo, jueces, gates, flags, modelos, routing, dependencias y workflows sin cambios. Stable permanece en `6d27ba4963ffe469d635db71eaeec506a8ff4b61`, sin cambios tracked; no se eliminan sus untracked existentes. Cero servicios iniciados/parados, descargas, generaciones, VLM o benchmarks GPU. No hace falta abrir servidores para esta preparación.

## Continuación concreta

La preparación y las dos revisiones quedan registradas; la validación perceptual permanece parcial. El [tablero v3 local](D:/Apps/MPT-worktrees/image-model-routing-modernization/local_image_stack/experiments/bridge/target/spatial-annotation-review-v3-2026-10-09/review-board.png) y los diagramas individuales permiten inspección con más detalle. Para B, resolver primero qué borde pertenece al metal y cómo tratar la perspectiva; no perseguir encaje perfecto moviendo el contorno hacia la forma esperada.

La siguiente tarea es diseñar una prueba acotada de componentes y límites de pose con los puntos aproximadamente revisados, conservando la máscara de B como discutida. Antes de calcular métricas, fijar correspondencias, incertidumbre y operaciones permitidas; el borrador propone traslación, rotación en plano y escala uniforme, sin estiramiento anisotrópico/reflexión ni normalización de perspectiva no calibrada. No hay tolerancia de aceptación ni negativo estructural de taza revisado: la calibración y la admisión siguen pendientes.
