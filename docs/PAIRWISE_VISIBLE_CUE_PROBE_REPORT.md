# Observación directa de pistas visibles — 2026-10-09

Desde `277f356cd492cb990aaf17047e8b5264a83339c8`, mismo worktree y rama experimental, inicio limpio y diez worktrees comprobados. Qwen3.5 produce cuatro observaciones estructuradas válidas; Qwen3-VL devuelve una combinación inválida en el primer control y su cohorte se detiene. Se ejecutan **cinco de las ocho consultas máximas**, sin reintentos, nuevas imágenes o descargas. Ningún candidato queda aprobado para QA automático.

## Implementación y prueba

Dos scripts aislados: `pairwise_cue_observations.py` recibe sujeto y descripción de pista como parámetros, construye el prompt/schema y valida seis campos; `observe_pairwise_cue.py` reutiliza transporte, runtime, modelos existentes, proceso propio y comprobación de regiones. No se cambia la aplicación MPT ni su QA, parser temporal, routing o gates.

Se reutilizan los cuatro fotogramas completos RGB preparados: mismo píxel/modo/dimensiones nativos, sin metadata auxiliar. El preflight reconstruye las fuentes y comprueba hashes/rectángulos antes de cargar y de cada HTTP; una región parcial no puede sustituir al fotograma completo. El [plan ejecutable](validation/pairwise-visible-cue-probe-plan-2026-10-09.json), SHA `9bb63661cb10713a839736047ca34e6e8bcf2977d5c912d8dd4cc0d771239d54`, fija ocho archivos de implementación y el [diseño anterior](validation/pairwise-visible-cue-design-2026-10-09.json). Los bytes del código no cambian después del test final ni entre consultas. Las respuestas no reciben ids, expectativas, captions, labels históricos o coordenadas.

Presencia y visibilidad de pista se distinguen por fotograma. Presencia ausente/incierta obliga a visibilidad incierta; la contradicción se rechaza, sin normalizarla. JSON inválido, campos extra, duplicados, truncación, reasoning o inconsistencia entre categorías de imágenes idénticas detienen la cohorte conservando raw. La consistencia del control idéntico no acredita que su descripción sea correcta. Cada diagnóstico válido conserva `identity_score`, `state_score` y `progression_score` separados y null, verdict `uncertain`, admisión/rechazo automático false. Un patrón visible no mide temperatura, identidad física, movimiento del líquido o progresión causal.

TDD: 44 RED iniciales del observador y 22 del runner, seguidos por GREEN; **182 tests finales pasan en 3,43 s, exit 0, sin avisos**, 66 nuevos y 116 anteriores. [Log final](validation/pairwise-cue-final-tests-2026-10-09.txt). Los tests incluyen cambios de fuente al cargar/entre envíos, sustitución por un recorte internamente válido, bindings del código, cero HTTP después de fallo local, parada por contradicción y cierre del contexto propio; proceso/HTTP de esas pruebas son simulados. Revisión independiente de código previa a inferencia sin hallazgos. Esos tests prueban el software y sus límites, no exactitud perceptual.

## Cohortes reales

Dos candidatos ya instalados, secuenciales, contexto8192/parallel1/256tokens/temperature0/sin thinking, máximo4 por candidato y0 retries. La pista genérica en esta cohorte son formas pálidas translúcidas junto a la abertura de la taza; no se pide «té caliente/frío» ni sustituir smoke por steam en captions anteriores.

| Par retenido | Qwen3.5: pista anterior → actual | Qwen3-VL |
|---|---|---|
| Referencia/referencia, bytes idénticos | not_observed → not_observed; consistente | JSON completo, presencia uncertain y pista not_observed en ambas; inválido |
| Referencia/cálido512 | not_observed → observed; hint de aparición | Sin ejecutar por parada |
| Referencia/caliente768 | not_observed → observed; hint de aparición | Sin ejecutar por parada |
| Caliente768/enfriado768 | observed → not_observed; hint de desaparición | Sin ejecutar por parada |

[Raw Qwen3.5](validation/pairwise-cue-qwen35-2026-10-09.json), [raw Qwen3-VL](validation/pairwise-cue-qwen3vl-2026-10-09.json), [análisis](validation/pairwise-cue-analysis-2026-10-09.json). Los cinco HTTP devuelven final content con stop y cero reasoning; cuatro pasan validación y uno queda `unavailable` por el contrato de presencia. Ese nombre de status no significa una caída HTTP: Qwen3-VL respondió y el parser rechazó sus categorías. Los tres casos restantes no se puntúan ni se presentan como fallos perceptuales. No se rescata la respuesta con otro prompt, tokens, crop o retry.

Las apariciones de Qwen3.5 concuerdan cualitativamente con la [inspección previa del asistente](validation/retained-temporal-assistant-visual-audit-2026-10-09.json), que ya conocía los labels y no es revisión humana ciega. En el último caso, Qwen3.5 declara not_observed y escribe que la zona es oscura; el prompt requería uncertain ante oscuridad/ambigüedad. Es un riesgo de incumplimiento semántico conservado, no corregido después para obtener un resultado favorable. El asistente también había marcado ambigua esa abertura. No se asignan accuracy, TP/TN/FP/FN o gold de ausencia; tampoco se convierte ese hint en prueba de enfriamiento o líquido inmóvil. Los tres QA históricos permanecen uncertain y sus captions/labels intactos.

| Modelo | Consultas | Válidas/inválidas | Media local, s | Mediana, s | Carga propia, s |
|---|---:|---:|---:|---:|---:|
| Qwen3.5-9B Q4_K_M | 4 | 4/0 | 5,712 | 5,727 | 4,029 |
| Qwen3-VL-8B Instruct Q4_K_M | 1 | 0/1 | 5,412 | 5,412 | 4,042 |

La parada impide una comparación de velocidad equivalente. Tiempos incluyen preparación del payload, preflight, HTTP y parseo; carga/readiness separada, sin contar todo el hashing inicial de pesos/runtime. Ambos reportan cero tokens cacheados en estas consultas. No hay p95 representativo, pico VRAM, ahorro de QA completo ni ranking poblacional a partir de n4/n1.

## Cierre y decisión

[Preflight de recursos](validation/pairwise-cue-resource-preflight-2026-10-09.json): RAM libre16,86GiB, GPU1119/12288MiB y14% de uso,8080/8092 libres,8090HTTP404 —respuesta, no readiness—,8188HTTP200/cola0/0. Antes de Qwen3-VL: primer PID ausente, RAM16,93GiB, mismos puertos libres y cola0/0. Get-CimInstance no tuvo acceso; GlobalMemoryStatusEx permitió comprobar RAM sin cambiar permisos. Runtime oficial dos ZIP/54 DLL-EXE y pesos/proyector rehasheados por cada inicio, sin descargarlos de nuevo.

Dos PID propios19704/18176 cerrados y comprobados ausentes;8092libre, cola0/0 yRAM17,04GiB al cerrar. GPU1123/12288MiB y26% es snapshot, no GPU completamente idle o pico de esta prueba. [Comprobaciones](validation/pairwise-cue-closing-checks-2026-10-09.json). Conservar logs ignorados bajo `target/pairwise-cue-qwen35-2026-10-09` y `target/pairwise-cue-qwen3vl-2026-10-09`, junto a los originales/fullframes. Servicios compartidos conservados; cero generación/descargas/deps/modelos/defaults/gates/routing/workflows/estable modificados. Solo se crean/cerran los dos servidores propios para esta prueba.

Qwen3.5 aporta evidencia estructurada útil en este protocolo; incertidumbre semántica y calibración independiente siguen pendientes. El fallo único de Qwen3-VL no demuestra incapacidad general ni justifica reabrir este contraste con cambios orientados al resultado. Se cierran ambas cohortes sin más consultas aquí y sin promoción.

Próximo paso autónomo CPU: auditar el punto de integración con el contrato QA existente y los huecos de evidencia, y preparar un plan de modo diagnóstico que conserve abstención/scores sin calibrar. Reutilizar selectividad/caché ya existentes; no añadir llamadas por escena por defecto, conectar un gate o asignar umbrales arbitrarios. Geometría/recuentos/estados con negativos válidos, etiquetas humanas independientes y latencia completa siguen necesarios antes de escoger y aprobar un juez automático. No requiere abrir8080 ni otra aprobación rutinaria.
