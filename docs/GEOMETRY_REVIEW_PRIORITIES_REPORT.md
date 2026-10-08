# Prioridades de revisión geométrica — 2026-10-08

Se implementó una política **offline de avisos**, sin aprobación ni rechazo automático, sobre las observaciones existentes. No se llamó al modelo ni a servicios de generación. La política separa señales del modelo de conclusiones humanas; nunca convierte una diferencia de conteo en una alteración grave o variación leve sin evidencia adicional.

Base ejecutada `61c1285a86c52c047803849fa966d99cab748283`, rama experimental limpia al inicio. Nuevo [triage_geometry_observations.py](../scripts/triage_geometry_observations.py), versión geometry-review-priorities-1. Se reutiliza el inventario ya validado, no cambia su schema/prompt ni las observaciones guardadas. No app/routing/config/dependencies/workflow/default changes.

## Política y límites

| Evidencia disponible | Prioridad de revisión |
|---|---|
| Modelo: aparece/desaparece un atributo | Revisar posible alteración estructural, sin confirmarla |
| Modelo: conteos distintos con misma presencia | Revisar medición; severidad desconocida |
| Modelo: atributo obscuro/count desconocido | Observación incompleta |
| Modelo: atributos coincidentes | Sin señal detectada; no establece identidad |
| Humano: cambio de forma | Cambio estructural reportado por humano |
| Humano: conservación con variación localizada | Variación localizada reportada por humano; tolerancia sin definir |
| Humano: conservación sin cambios, modelo discrepa | Auditar desacuerdo modelo/humano, conservar ambos datos |
| Humano: duda | Revisión humana inconclusa |
| Inventario ausente/invalid/transport incompleto | unavailable, solicitar observación válida; revisión humana no repara modelo |

Todas las prioridades conservan admission_allowed=false,automatic_rejection=false y physical_identity_established=false. Con inventarios válidos, statusuncertain; con evidencia ausente/invalid, unavailable. Una revisión ya recibida se distingue de una pendiente y no se pide otra vez el mismo A/B/C. La incertidumbre del modelo no desaparece cuando llega la revisión humana. Shape/localized_change/note/source están tipados; source debe ser human. Esto valida un contrato de datos, no autentica por sí solo a cualquier productor externo: el replay actual utiliza los mensajes humanos del usuario ya registrados con hashes.

Las descripciones libres no deciden severidad ni se analizan buscando palabras positivas/negativas. Los datos solo son observaciones cualitativas; no se estiman proporciones físicas de imagen/perspectiva ni tamaño de anillos. La variación leve de A proviene de la anotación humana, **no de una nueva capacidad perceptual del modelo**. Los conteos de C quedan visibles, no se silencian por conocer su case_id. La política no conoce IDs/objetos específicos para escoger prioridades; el replay usa IDs/hashes únicamente para vincular evidencias.

## Replay A/B/C, sin nueva inferencia

[Inputs normalizados con provenance](validation/geometry-review-priority-inputs-2026-10-08.json), [salida reproducida](validation/geometry-review-priority-replay-2026-10-08.json). La normalización conserva literalmente cada respuesta humana y deriva: A preserved+localized_change, B changed, C preserved+no localized_change. Histórico/dataset/respuestas/anotaciones originales intactos.

| Par | Solo modelo | Con revisión humana |
|---|---|---|
| A | Sin señal detectada | Conservación general con variación localizada reportada |
| B | Revisar estructura | Cambio estructural reportado |
| C | Revisar conteos | Desacuerdo entre modelo y humano |

Los tres conservan uncertain/no admisión. No recalcular precisión como si estos tres pares fueran una nueva muestra perceptual: se reusan los mismos inventarios y la política fue diseñada después de conocer la revisión. No declarar validado un umbral ni ocultar que el modelo omitió tamaño en A y dio falsas alarmas en C.

## Validación y siguiente tarea

87 tests offline pasan,exit0,2.88s ([log](validation/geometry-review-priorities-tests-2026-10-08.txt)):18 nuevos de prioridades/provenance/fail-closed +69 previos. Casos adicionales sintéticos cubren ausencia de inventario, incertidumbre, conteos/presencia, discrepancia humana, anotación mal tipada/modelo presentado como humano, SHA de imágenes distinto, IDs duplicados y transporte incompleto. Son controles de software; no nuevas imágenes ni validación de percepción.

Replay3 pares,0model/GPU/generation requests,0automatic decisions. Revisar JSON,hashes,secret patterns,diff y estable al cierre ([checks](validation/geometry-review-priorities-checks-2026-10-08.json)). El commit de cierre se obtiene del historial; no se incluye como self-reference. No tests históricos se atribuyen a otro cambio:87 es la ejecución nueva de esta política.

Siguiente tarea concreta: ampliar controles perceptuales con otra familia de objetos usando artifacts existentes y conservar una evaluación separada de severidad/incertidumbre. Antes de conectar avisos al diagnóstico MPT, validar esas prioridades fuera de estos tres pares. La eventual integración será opt-in de diagnóstico, sin capacidad de pasar gates ni rechazar escenas basándose únicamente en este modelo; debe mantener OCR/checks deterministas y fail-closed factual. No se implementa aquí esa integración ni se necesita cambiar modelos/workflows para este replay.
