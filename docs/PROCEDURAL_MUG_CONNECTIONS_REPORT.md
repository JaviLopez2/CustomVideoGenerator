# Controles procedurales de conexiones — 2026-10-11

## Ejecución cerrada — contrato de estado inválido en ambos jueces

Desde `66d019b91884909be909eb40cbb548386af8527c`, se ejecutaron **dos consultas reales**, una por juez, dentro del máximo declarado de seis. Ambos devolvieron HTTP200, una respuesta completa `stop` y cero reasoning; en el control idéntico reportaron estructura/conexiones `not_observed` pero estado `not_applicable`. El scope declara vapor permitido, por lo que ese estado es inválido incluso cuando no hay vapor visible. Cada cohorte se detuvo en la primera observación rechazada, sin retries: **vapor y unión rota no se consultaron**. No se concede pass al control ni detección/omisión del defecto no evaluado.

[Raw Qwen3.5](validation/procedural-mug-connections-qwen35-2026-10-11.json), [raw Qwen3-VL](validation/procedural-mug-connections-qwen3vl-2026-10-11.json), [análisis](validation/procedural-mug-connections-analysis-2026-10-11.json). La fila del observador se conserva como `transport_status=unavailable`, pero el análisis distingue la causa real: rechazo del contrato tras HTTP exitoso, no caída de red/servidor. Q35 describe ausencia de vapor; VL pone `not_applicable` también en la evidencia de estado. Los literales y raw choices permanecen intactos, sin reparar enums o inventar los cuatro casos no intentados.

Discrepancia comprobada con `jsonschema.validate` y el validador publicado: las dos respuestas satisfacen el JSON schema genérico, que ofrece `not_applicable`, pero fallan `observer.validate` con `State observation contradicts declared scope`. Esto justifica alinear el schema experimental con los estados declarados antes de más inferencia; no convierte el resultado actual en un acierto geométrico ni elimina los fallos naturales anteriores.

[Plan de ejecución v2](validation/procedural-mug-connections-execution-plan-v2-2026-10-11.json), [recipe v2](validation/procedural-mug-connections-execution-recipe-v2-2026-10-11.py). Pins de preparación/resultado/píxeles/observer/runner/HTTP/assets/runtime, roles y solicitudes comprobados antes de cada consulta. Pesos/projectors existentes y runtime b11497 rehashados por cohorte; 54 archivos extraídos verificados, sin descargas. Recursos verificados antes y después del hashing, un servidor oculto propio 8092 por vez; servicios compartidos sin controlar.

Un P2 de revisión detectó pérdida de cuerpos HTTP inválidos/de error en el transporte original. [Dos RED sin red](validation/procedural-mug-connections-transport-red-2026-10-11.json) lo reproducen; código/plan de ejecución v1 se conservan como antecedente sin consultas. V2 guarda bytes completos en base64, SHA, tamaño y status antes de parsear; HTTPError conserva su cuerpo y el fallo sin respuesta se distingue con campos null. [GREEN](validation/procedural-mug-connections-execution-green-controls-2026-10-11.json): cuatro controles offline de transporte y nueve alteraciones del plan rechazadas, sin retry. Los dos cuerpos reales están ligados a sus raw choices, verificados byte por byte; no se guardan requests de imágenes o credenciales.

**[Final: 147 tests pertinentes pasan, 2,10 s/exit 0](validation/procedural-mug-connections-execution-final-tests-2026-10-11.txt)**; son tests existentes, ejecutados de nuevo después de la corrección. [Run previo](validation/procedural-mug-connections-execution-tests-2026-10-11.txt):147/2,27s, antes del fix; no se confunden ambos. [Controles CPU iniciales](validation/procedural-mug-connections-execution-cpu-controls-2026-10-11.json) también se conservan.

Preparación de payload 0,0015/0,0016 s; verificación transitiva+HTTP+parsing 5,152/5,234 s y carga propia 4,043/4,044 s. Cached tokens0/0. No son QA completo de MPT, p95, pico VRAM o comparación causal de velocidad. [Recursos al cierre](validation/procedural-mug-connections-resource-closing-2026-10-11.json): PID25528/22376 ausentes (`OpenProcess` error87),8092 libre,RAM17,22GiB,GPU1786/12288MiB y3%.8080 cerrado;8090HTTP404 solo liveness;8188HTTP200. Cero retries/generaciones/descargas/benchmarks o cambios de app/gates/routing/deps/workflows/estable. [Checks de ejecución](validation/procedural-mug-connections-execution-closing-checks-2026-10-11.json); SHA final mediante Git/origin.

Siguiente autónomo CPU: schema compatible con el estado declarado y matriz/replay de respuestas archivadas para probar la alineación. Conservar el observador y todas las cohortes cerradas; no reparar sus salidas o inferir geometría no consultada. El objetivo continúa activo. Ningún juez queda aprobado para geometría y no hace falta intervención del usuario para esta corrección.

## Preparación publicada en 66d019b — histórico, anterior a la ejecución

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
