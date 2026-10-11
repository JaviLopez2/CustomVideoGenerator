# Controles procedurales de conexiones — 2026-10-11

Se preparan tres pares de una taza dibujada por código para comprobar la separación entre estructura y estado permitido: imagen idéntica, aparición de vapor con el asa intacta y pérdida de la unión inferior con el mismo vapor. **No se ejecuta inferencia.** Las etiquetas describen una construcción conocida; no son gold humano, precisión sobre fotografías ni aprobación de un juez.

Base: `76acc31257a5e915e7f6cf118ed203cb53ff7c5b`, rama experimental `factory/image-model-routing-modernization`. La revisión humana de cámara/foto ya recibida y las cohortes anteriores se conservan. Esta familia procedural permite un control de conexión claro, pero no sustituye los defectos de imágenes reales ni acredita identidad.

## Inputs fijados y prueba de píxeles

[Recipe v2](validation/procedural-mug-connections-recipe-v2-2026-10-11.py), [plan v2](validation/procedural-mug-connections-plan-v2-2026-10-11.json), [preparación v2](validation/procedural-mug-connections-preparation-v2-2026-10-11.json). Tres PNG únicos RGB8 de 512×512, dibujados mediante primitivas geométricas, sin modificar fotografías, descargar pesos o generar con modelos. El asistente inspeccionó los tres: cuerpo y asa construidos dentro del canvas, con separación visible en la unión inferior del tercero. No hay nueva adjudicación humana.

La prueba deriva de los RGB renderizados, usando caminos de foreground con ocho vecinos dentro de ventanas locales fijas. Ambos extremos de cada camino deben estar presentes; la ausencia de un punto no cuenta como unión rota. La unión superior permanece conectada en los tres. La inferior está conectada en los dos primeros y desconectada en el tercero. El cuerpo conserva exactamente sus píxeles y el par con defecto conserva exactamente el vapor. Solo cambian **968 píxeles**, caja `[341,409,385,431]`, en el terminal inferior del asa. Son mediciones de estos diagramas; el algoritmo no se propone como detector de verdad física para imágenes naturales.

| Par | Estructura esperada por construcción | Conexiones | Estado permitido |
|---|---|---|---|
| Taza sin vapor → misma imagen | not_observed | not_observed | not_observed |
| Taza sin vapor → taza intacta con vapor | not_observed | not_observed | observed |
| Taza intacta con vapor → unión inferior rota, mismo vapor | observed | observed | not_observed |

El scope protege cuerpo, asa y sus conexiones permanentes, y permite vapor visible sobre el borde. Se mantiene el protocolo publicado `scoped-structure-state-observations-1`; no se modifica app ni observador. Prompt, schema, roles e inputs están ligados por SHA. Nombres de casos, etiquetas esperadas, rutas, metadata y coordenadas no se envían en los payloads. El vapor procedural es una señal visible; no acredita temperatura.

Presupuesto declarado para una futura cohorte separada: tres consultas por cada juez existente, máximo seis, cero retries/descargas/generaciones con modelos, 512 tokens, temperatura 0, thinking false, contexto 8192 y tokens de imagen 1024–1536. La receta actual solo acepta operaciones CPU. Antes de esa cohorte habrá que ligar ejecución, pesos/runtime, recursos y cierre del servidor propio; el presupuesto no acredita consultas ya realizadas.

## Revisión, corrección y validación real

La revisión independiente encontró un P2: v1 no comprobaba el SHA del plan guardado en el resultado de preparación ni sus claims. [Reproducción RED](validation/procedural-mug-connections-review-red-2026-10-11.json): claims y timestamp alterados aceptados, sin tocar el plan original o ejecutar modelos. [V1](validation/procedural-mug-connections-plan-2026-10-11.json) y sus código/resultado/píxeles se conservan como antecedente **no apto para inferencia**.

V2 fija las limitaciones, verifica el enlace RESULT→PLAN y los claims de cero consultas/generaciones y sin gold humano, además de cronología, píxeles, labels, scope, schema y requests. La comprobación interna anterior a crear RESULT es explícita; `--verify-only` exige RESULT. Los tres PNG y payloads coinciden entre v1/v2. [Doce controles rechazados](validation/procedural-mug-connections-cpu-controls-2026-10-11.json): claims, fecha, presupuesto numérico/booleano, scope, label, request, pin, roles y resultado/enlace/gold/consultas. Sustituciones de snapshots en la misma ruta evitan atribuir el rechazo a una ruta alternativa; originales conservados.

**[147 tests pertinentes pasan de nuevo, 2,27 s, exit 0](validation/procedural-mug-connections-tests-2026-10-11.txt)**; son tests existentes del observador, preflight/runner pareados y preparación de regiones, no tests nuevos ni precision visual. Python MPT `-B -m pytest -q test/test_scoped_structure_observations.py test/test_paired_shape_observations.py test/test_paired_shape_preflight.py test/test_paired_shape_runner.py test/test_prepare_visual_regions.py --tb=short`, integración desactivada. Sin cambios de app, gates, defaults, routing, modelos configurados, dependencias, workflows, servicios o copia estable. [Checks finales](validation/procedural-mug-connections-closing-checks-2026-10-11.json); SHA publicado mediante Git/origin.

## Siguiente acción

Ejecutar una única cohorte declarada de hasta seis consultas, con los jueces ya instalados y los recursos comprobados antes de cada cohorte, guardando raw y cerrando solo procesos propios. Un fallo en estos controles cuestionaría el uso del protocolo como guardia estructural; un acierto solo sería una comprobación procedural, no calibración natural o elección de juez geométrico. No repetir una cohorte cerrada para rescatar un resultado. El objetivo continúa activo y no hace falta otra revisión humana para estos controles.
