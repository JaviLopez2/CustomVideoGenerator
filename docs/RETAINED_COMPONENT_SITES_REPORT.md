# Localización de componentes retenidos — 2026-10-09

**Qwen3.5 separa los contactos de la taza roja, pero no los localiza de forma consistente en la azul. Qwen3-VL agrupa ambos sitios en una sola caja en las dos tazas.** Ambos alcanzan el punto central del hueco del asa; ese resultado no demuestra precisión del contorno ni permite escoger un juez automático de identidad.

Base publicada `5c718730f1d94b0f5e90ab6a410966c0956e74a9`, rama `factory/image-model-routing-modernization`, worktree Windows experimental. Carpeta, rama, HEAD, status, diffs staged/unstaged y diez worktrees verificados; inicio limpio. Se ejecutó una auditoría offline aislada, sin modelos o servicios. HEAD de ejecución y SHA del checkpoint posterior son distintos; consultar Git/origin para el cierre.

## Entradas y alcance

[Plan fijado antes del cálculo](validation/retained-component-sites-plan-2026-10-09.json): cuatro raw del protocolo de un componente por solicitud, sus dos perfiles, anotación v3 y ambas revisiones humanas, todos vinculados por SHA. Se releen 12 respuestas históricas: ocho observaciones positivas sobre las dos tazas y cuatro casos sin taza. El JSON final se vuelve a validar y debe coincidir con el inventory guardado; también se comprueba el replay del coverage original. No se reparan cajas, prosa o respuestas truncadas.

Es una revisión retrospectiva, con las salidas ya conocidas antes del plan, no un ensayo ciego ni un dataset de evaluación independiente. Los puntos fueron dibujados por el asistente y el usuario dijo que parecían coincidir a la escala del tablero. Esa revisión aproximada no certifica una tolerancia por píxel. Los círculos de radio3px son el margen de dibujo preexistente, no una confianza estadística ni una cota demostrada del error real.

El hueco se contrasta únicamente con `handle_opening_center`; los contactos, con `upper_handle_attachment` y `lower_handle_attachment`. Comparaciones dentro de cada imagen; no emparejamiento físico entre fotos, ajuste de perspectiva, máscaras o scores de identidad. Las seis fotos, v3, A/B/C y ambas respuestas humanas permanecen intactas. B sigue fuera de mediciones de máscara completa y no participa en este cálculo.

## Método y controles

Se conserva la convención del renderer existente: `x*width/1000`, `y*height/1000`, en la extensión continua de la imagen completa. Las cajas enteras0–1000 se convierten a píxeles fraccionarios sin redondear, mover o recortar. No se añade una tolerancia por cuantización de las cajas; son exactamente las coordenadas reportadas, cuya incertidumbre real se desconoce.

Para cada punto/caja: disco contenido, disco que alcanza el borde o disco separado. Se guardan margen firmado, distancia nominal y distancia mínima condicionada al radio supuesto. Son relaciones geométricas de anotaciones/boxes, no presencia verdadera o ausencia física de una pieza.

Se distingue alcance de puntos de separación: una caja amplia puede alcanzar dos sitios sin aportar dos localizaciones. Matching requiere cajas distintas por sitio; matching exclusivo exige además que cada caja alcance solo un disco declarado. Dos cajas amplias diferentes que alcancen ambos sitios tampoco acreditan separación exclusiva. Para un único centro de hueco, incluso una caja de imagen completa lo alcanza: se conserva su área relativa y `mask_precision_verified=false`, sin convertir cobertura central en segmentación.

Controles de tests: bordes fraccionarios, tangencias, entradas inválidas, una caja para dos sitios, dos cajas amplias, dos cajas sobre el mismo sitio, regiones pequeñas separadas, ausencia de boxes, caja de imagen completa, inventory alterado, truncación y target ausente. Ningún test exige que un modelo real pase ni modifica los raw.

## Resultados locales condicionados a las anotaciones

[Raw de la auditoría](validation/retained-component-sites-results-2026-10-09.json): 12 replays, ocho diagnósticos, 14 relaciones disco/caja y ocho SVG. Cuatro outputs de target ausente quedan no aplicables, sin asignarles un cero de contactos o precisión.

| Modelo / taza | Hueco: disco central contenido | Contactos: cajas | Discos contenidos / alcanzados | Sitios separados de forma exclusiva: contenidos / posibles |
|---|---|---:|---:|---:|
| Qwen3.5-9B / roja | Sí | 2 | 2 /2 | 2 /2 |
| Qwen3.5-9B / azul | Sí | 1 | 0 /1 | 0 /1 |
| Qwen3-VL-8B / roja | Sí | 1 | 1 /2 | 0 /0 |
| Qwen3-VL-8B / azul | Sí | 1 | 1 /2 | 0 /0 |

Qwen3.5 roja: los puntos superior/inferior quedan en cajas distintas, con márgenes nominales8,40/4,40px, mayores que el radio supuesto3px. Azul: punto superior nominalmente dentro por solo0,16px, por lo que el círculo no cabe entero; el inferior está a118,48px de la única caja (cota condicionada mínima115,48px). No se transforma ese borde incierto en una localización verificada.

Qwen3-VL: una caja vertical abarca los dos puntos nominales en cada imagen. El círculo superior cruza el borde (margen1,16px roja/0,16px azul), el inferior cabe (9,52px). La región se conserva como agrupada/ambigua; la palabra “two” de la prosa azul no crea una segunda caja ni un conteo factual.

Huecos: las cuatro cajas contienen el centro y el disco supuesto. Las cajas de Qwen3-VL son más amplias; cubrir el centro con mayor margen no demuestra mayor precisión. No se calcula IoU contra el polígono de hueco aproximado ni tasas TP/FP/accuracy, y no se calibra un umbral de aceptación con estas dos imágenes.

## Validación, aislamiento y preservación

Herramienta `scripts/audit_retained_component_sites.py`, tests `test/test_retained_component_sites.py`. Reutiliza solo validadores locales existentes; no llama a payloads, modelos, API o QA productivo. TDD real: RED24 fallos del esqueleto; GREEN24 aprobados; logs originales conservados. Plan/SHA fijados antes de la ejecución completa.

```powershell
$env:MPT_RUN_INTEGRATION_TESTS = '0'
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_retained_component_sites.py test/test_visual_location_observations.py test/test_spatial_annotation_review.py test/services/test_visual_observation_diagnostics.py test/services/test_visual_qa.py
```

**138 passed, 5,16s, Python exit0, sin warnings** en esta ejecución: 24 nuevos, 23 de localización, 16 de anotaciones y 75 de QA/diagnósticos. [Log actual](validation/retained-component-sites-final-tests-2026-10-09.txt), [cierre](validation/retained-component-sites-closing-checks-2026-10-09.json). La suite124 de la fase anterior se conserva histórica; no se repite la prueba de pose ni SIFT.

Ocho SVG/PNG y un [tablero de contactos](D:/Apps/MPT-worktrees/image-model-routing-modernization/local_image_stack/experiments/bridge/target/retained-component-sites-2026-10-09/contacts-board.png) en el directorio ignorado `target/retained-component-sites-2026-10-09`. SVG incrusta los bytes originales sin modificarlos; figuras y tablero revisados visualmente por el asistente. No es una nueva revisión humana de boxes o un certificado por píxel. Render con Node/sharp/Pillow existentes; caché Fontconfig externa no escribible, ocho renders exit0, sin cambios de permisos/configuración ni navegador/servidor. Conservar estos artifacts junto a los anteriores originales, borradores y runtime al archivar.

0 nuevas inferencias, generaciones, descargas, benchmarks GPU o servicios iniciados/parados. App, jueces, gates, flags, modelos, routing, dependencias, workflows y validadores previos sin cambios. Fetch0/0; stable permanece en6d27ba4, tracked limpio, untracked previos preservados. Escalaciones Git específicas no conceden permisos permanentes.

## Decisión y siguiente prueba concreta

Los dos candidatos mantienen autoridad de diagnóstico experimental. La separación de contactos de Qwen3.5 en roja no es consistente en azul; Qwen3-VL no separa esos sitios en estos outputs. No se habilita admisión de identidad ni se cambia el modelo de MPT.

Para avanzar hacia una elección falta un negativo estructural de taza claro y revisado, además de positivos. La siguiente tarea es preparar un protocolo mínimo con la taza roja retenida como positivo y una variante con una unión del asa visiblemente interrumpida como negativo; preservar composición y confirmar primero que el control realmente muestra ese cambio. Declarar presupuesto, revisión y criterios antes de cualquier nueva edición/inferencia. Esta fase termina con la auditoría offline; el protocolo del control estructural es la siguiente tarea. No seguir modificando prompts solo para reparar estas respuestas históricas.
