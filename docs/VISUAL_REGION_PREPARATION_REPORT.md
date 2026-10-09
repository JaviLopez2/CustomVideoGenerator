# Preparación reproducible de regiones — 2026-10-09

Desde `35059e1fa1154f17d165f8f6ef8b7dcbee47a0f4`, en el worktree y rama experimental actuales. Se añade una API offline de preparación de PNG y una cohorte CPU. No se ha ejecutado otra consulta a un juez ni generación.

## Contrato y límites

`scripts/prepare_visual_regions.py:prepare(plan, output_dir, workspace_root=...)` recibe el protocolo `visual-region-preparation-plan-1`: margen entero y entre una y dieciséis regiones. Cada región fija id, path/SHA/dimensiones de fuente, caja `xyxy` entera en coordenadas originales y, opcionalmente, la caja que debe contener. Solo el margen puede recortarse al límite de la imagen; una caja declarada fuera de límites se rechaza.

La herramienta lee una instantánea para hash y decodificación, conserva modo RGB/RGBA y valores nativos de los píxeles, sin resize, conversión de color, máscara o interpolación. Rechaza formatos distintos de PNG, perfiles ICC, orientación que requiera transformación y transparencia PNG `tRNS` no soportada. Elimina los metadatos auxiliares, incluidos textos de prompt/workflow, sin imprimir sus valores. El manifiesto conserva procedencia, cajas solicitadas/efectivas, margen, modo/dimensiones/hash del resultado y versión de Pillow.

Toda la cohorte se valida antes de crear el directorio. El destino debe estar dentro del workspace suministrado y ser nuevo; los archivos se crean en exclusiva. Un error de escritura posterior puede dejar artifacts parciales: conservarlos y diagnosticar, sin sobrescribirlos ni borrarlos. La API no altera modelos, aplicación, routing o gates.

`contained`, `partial`, `disjoint` y `not_declared` describen **relaciones entre rectángulos**. `whole_declared_region_eligible` es elegibilidad técnica, no prueba de que una caja corresponda al objeto completo. `semantic_coverage_review` queda `pending`; `admission_allowed` y `physical_identity_established` son siempre false. No es un localizador automático ni una comprobación de identidad.

## Prueba conservada y revisión

TDD inicial: treinta fallos con stubs, luego treinta pasan. Una regresión adicional reprodujo que modificar la lista de dimensiones de entrada alteraba la procedencia devuelta en memoria; copia defensiva y 82 tests enfocados pasan en 0,37 s. Esos resultados iniciales se conservan como históricos.

La revisión independiente detectó que eliminar `tRNS` de un PNG RGB conservaba los bytes RGB pero convertía un píxel transparente en opaco. Se reprodujo **antes de corregir**: 1 failed, 31 passed en 0,38 s. Ahora ese formato se rechaza. Resultado final: **83 passed en 0,39 s, exit 0, sin avisos**, 32 nuevos de preparación y 51 del observador/runner pareado existente. [Log final](validation/visual-region-preparation-final-v2-tests-2026-10-09.txt). Revisión final sin hallazgos. No se atribuyen los 216 tests históricos del parser temporal a este nuevo código; la aplicación no se modifica en esta fase.

Los planes, recetas, resultados y logs iniciales permanecen intactos. La receta inicial se liga al helper anterior, archivado junto a sus artifacts; ejecutarla contra el helper corregido se rechaza por SHA. [Plan v2](validation/visual-region-preparation-plan-v2-2026-10-09.json) y [receta v2](validation/visual-region-preparation-recipe-v2-2026-10-09.py) registran el único ajuste de compatibilidad, sin cambiar fuentes, cajas o margen. Las recetas pertenecen al HEAD base y rechazan cambio de bindings/destino existente; son evidencias históricas, no comandos para sobrescribir resultados.

## Cohorte real

Se usan las seis imágenes y cajas de la auditoría espacial anterior, fijadas antes de las consultas de forma, más dos recortes de la misma taza roja. Margen uniforme de 8 px, sin ajuste por resultado. Se prepararon ocho PNG en cada una de dos cohortes CPU —inicial y corregida—; todos los resultados v2 son **idénticos en bytes** a los iniciales. NumPy verifica independientemente los subconjuntos nativos y su modo; los metadatos de los recortes están vacíos.

| Entradas finales | n | Relación con la caja requerida | Resultado técnico |
|---|---:|---|---|
| Cuatro llaves | 4 | contained | Idénticas en bytes a los cuatro recortes de la cohorte pareada anterior |
| Tazas roja y azul | 2 | contained | 313 × 286 RGB; fuente y píxeles verificados |
| Taza roja parcial | 1 | partial | 313 × 181 RGB; corta la zona inferior, no elegible para comparar el objeto completo |
| Fondo de taza roja | 1 | disjoint | 104 × 104 RGB; no intersecta la caja declarada, no elegible |

La inspección directa del asistente ve cuerpo, borde y asa dentro de los dos recortes completos; el parcial corta base/unión inferior y el último muestra fondo desenfocado. [Preflight visual](validation/visual-region-assistant-preflight-2026-10-09.json). Es una valoración del asistente, sin nuevas etiquetas humanas, cuentas de contactos, máscaras gold o mediciones perceptuales. La cobertura humana sigue pendiente. Ninguno de los controles de cobertura es una imagen de defecto estructural; no reemplazan las microediciones de taza cerradas como inutilizables.

[Resultado v2](validation/visual-region-preparation-result-v2-2026-10-09.json) liga fuente, helper, receta, manifiesto y cada crop. Conservar los dos directorios ignorados `local_image_stack/experiments/bridge/target/visual-region-preparation*-2026-10-09`, incluidos el helper inicial archivado y manifiestos. Los PNG no se añaden al commit. [Cierre](validation/visual-region-preparation-closing-checks-2026-10-09.json).

## Próxima tarea

[Diseño fijado](validation/cross-family-roi-probe-design-2026-10-09.json): dos pares de bytes idénticos —roja consigo misma y azul consigo misma— como controles de consistencia, más el par conservado roja/azul. Sin gold humano de forma para ese último: observación raw, sin matriz de precisión. Máximo seis solicitudes, tres por cada juez existente, secuenciales; cero retries/generación/descarga. Los recortes parcial y de fondo deben excluirse **antes de inferencia**, con cero solicitudes. Dos controles duplicados y un par no permiten medir precisión poblacional ni sensibilidad a defectos.

Antes de ejecutar, extender y probar el runner experimental para procedencia de evidencia explícita: controles por construcción frente a comparación sin gold, conservando el protocolo v1 de A/B/C humano. Validar bindings/cobertura/píxeles del manifiesto antes de iniciar el PID propio. El diseño todavía no es un plan ejecutable. Mantener prompt/schema/decoding existentes; fijar el plan tras tests/revisión, comprobar recursos y servicios y ejecutar una sola cohorte por modelo. La fiabilidad temporal multimodal directa sigue pendiente. Continuación autónoma activa, sin intervención humana para esta preparación siguiente.
