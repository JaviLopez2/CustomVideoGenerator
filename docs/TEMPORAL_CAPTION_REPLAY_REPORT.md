# Replay temporal y negación explícita — 2026-10-09

Los tres casos temporales archivados siguen **uncertain** con v2, v3 y v4. Corregir interpretación de captions no recupera pistas visuales que el extractor omitió. El replay identifica además siete errores en diez controles de negación literal; el parche v4 los corrige sin promover el QA ni reinterpretar los labels originales.

## Evidencia retenida

Base `d636da6039089694aed7a6825d141a33a8a4ec57`, worktree/rama experimental, inicio limpio y diez worktrees. [Plan fijado antes de ejecutar](validation/temporal-caption-retained-replay-plan-2026-10-09.json). Dataset y resultado final08-10 fijados por SHA. Se rehashan los cuatro PNG únicos de candidatos/anteriores/referencia y se liga cada caption/OD a `image_sha256` y task, sin sustituir una observación por otra imagen ni inferir de nuevo.

El [recipe CPU congelado](validation/temporal-caption-retained-replay-2026-10-09.py) carga el módulo QA puro v2 del Git417dac3, importaciones locales verificadas; ambos motores reciben únicamente un adaptador de observaciones archivadas. Comprueba que el replay v2 reproduce exactamente los checks/verdict históricos y que v3 realiza las mismas lecturas. No instancia Florence ni llama a HTTP. Su manifiesto fija el estado v3 ejecutado y rechaza cambios de fuente/salida existente; no es un CLI que deba sustituir fuentes silenciosamente con el HEAD futuro. [Resultado v2/v3](validation/temporal-caption-retained-replay-2026-10-09.json). El [replay v4](validation/temporal-caption-retained-replay-v4-2026-10-09.json) reutiliza solo el adaptador/digest verificados por SHA mediante AST, sin ejecutar de nuevo el cuerpo del recipe ni sobrescribir el informe v3.

| Caso retenido | Expected histórico del asistente | QA v2 | QA v3 | QA v4 | Evidencia insuficiente |
|---|---|---|---|---|---|
| temporal_warm_512 | pass | uncertain | uncertain | uncertain | Caption usa smoke; falta steam literal y evidencia de transición |
| mpt_temporal_hot_768 | pass | uncertain | uncertain | uncertain | Mismo límite de vocabulario/extracción; count también incierto |
| mpt_temporal_cooled_768 | uncertain | uncertain | uncertain | uncertain | No establece still liquid ni ausencia explícita de steam |

No se reemplaza smoke por steam para buscar pass. Labels de la colección proceden de revisiones del asistente, no de adjudicación humana independiente; el estado frío continúa incierto. Times guardados en el replay son **CPU de lógica sobre evidencia ya obtenida**, con timings de inferencia del adaptador a cero y marcado `archived_replay`. No son nuevas mediciones de Florence/judge ni latencia end-to-end.

## Negación: causa y parche

Diez controles de lenguaje independientes de las fotos, con política literal declarada por el asistente antes de probar. V3 daba pass a requerido «Frost is absent», «Frost is not visible», «isn't any frost» y «free of frost»; daba fail a prohibido «Smoke is absent». También trataba dos dobles negaciones como estados ciertos.7 desacuerdos, no una métrica de precisión visual. V4 concuerda con esos10 controles.

Solo cambia `app/services/visual_qa.py` y se añade `test/services/test_visual_qa_state_negation.py`: ausencia posterior con cópula, palabras absent/missing o negación explícita de visibilidad/presencia; contracciones negativas y free/devoid of anteriores; dobles negaciones conservadas uncertain. Apostrofo tipográfico se normaliza solo para parseo, sin reescribir el caption archivado. La negación de otra propiedad, como «frost is not blue», no se convierte en ausencia del término. Cláusulas/cualificación/contradicción y separación de identidad/estado/progreso de v3 se conservan.

La revisión encontró dos límites reales:24 caracteres descartaban negadores con modificadores admitidos y «not completely free of» escapaba a doble negación. Se reprodujeron seis casos required/forbidden antes de corregir: prefijo completo de la cláusula con proximidad aún limitada por palabras y0–1 modificador genérico antes de free/devoid of/without. Revisión final sin hallazgos. `VERSION=visual-qa-4` invalida caches v3; un test siembra el pass incorrecto v3 y verifica recomputación fail. No nueva capa de cache, flags, defaults o integración activada.

## Pruebas y cierre

30 regresiones nuevas: signos required/forbidden, contracciones/apóstrofo tipográfico, pistas multiword, wrapping, calificadores, propiedad distinta, contradicción, doble negación/modificadores, progresión previa y cache v3. CPU, sin modelos ni red.

- RED inicial18 failed/6 passed,0,40s/exit1: [log](validation/temporal-negation-red-tests-2026-10-09.txt). El primer stdout se decodificó con sustitución UTF8 y algunas apariciones del apóstrofo tipográfico quedan como replacement en ese log; el literal del fixture y el nombre escapado del caso son correctos. Se conserva esa salida, sin presentarla como captura exacta de todos los bytes.
- GREEN100 passed,3,21s/exit0: [log](validation/temporal-negation-green-tests-2026-10-09.txt).
- RED de revisión6 failed/24 passed,0,37s/exit1: [log](validation/temporal-negation-review-red-tests-2026-10-09.txt).
- **Final216 passed,6,67s/exit0/sin avisos**,30 nuevos+186 previos: [log](validation/temporal-negation-final-tests-2026-10-09.txt). Estos runs posteriores fijan PYTHONIOENCODING=utf8 solo en el proceso de tests, sin configuración global.

Comando final con Python MPT y MPT_RUN_INTEGRATION_TESTS=0: `-B -m pytest -q test/services/test_visual_qa_state_negation.py test/services/test_visual_qa_state_evidence.py test/services/test_visual_qa.py test/services/test_visual_observation_diagnostics.py test/services/test_klein4b_mpt.py test/services/test_corrective_continuity.py test/services/test_evidence_pruning_root_qa.py`. QA/gates/continuidad/diagnóstico/Klein incluidos. [Cierre verificable](validation/temporal-negation-closing-checks-2026-10-09.json); raw RED con whitespace propio de pytest conservado y separado de fuente/docs.

0 nueva generación, VLM/Florence, GPU/benchmark, descarga, dependencias, modelos, workflows activos, servicios, Factory o estable. No se borra cache ni se cambia routing/política de admisión. El contraste visual de forma anterior conserva sus12 consultas y datos separados; no se atribuyen a este parche.

## Continuación

El parser sigue siendo léxico inglés y acotado, sin resolución universal de negación, sujeto o temperatura física; fuera de los formatos cubiertos no se afirma fiabilidad. Su conformidad en ejemplos de lenguaje no calibra un juez visual ni solventa los captions retenidos. Cerrar esta auditoría y preparar regiones source-bound reproducibles con controles de cobertura y otra familia para contrastar el candidato ROI; no más ajustes de texto para conseguir un pass en estas fotos. La evidencia temporal visual fuerte sigue pendiente y puede requerir observaciones directas multimodales sobre las imágenes existentes. Sin producción/gate/routing promovidos; autonomía activa y siguiente preparación CPU sin intervención humana.
