# Klein 4B: bloque autónomo — 2026-10-08

## Estado inicial y alcance

Worktree `image-model-routing-modernization`, rama `factory/image-model-routing-modernization`, HEAD `1c7de1a707f0d51a631e027631f0da939567284b`, limpio; fetch origin sin divergencia. Stable en `6d27ba4963ffe469d635db71eaeec506a8ff4b61`. Instrucciones/handoffs leídos; no se repitieron las fases de instalación, construcción del bridge o pruebas históricas.

Autorización: integración y pruebas iterativas experimentales, incluyendo GPU secuencial. Se ejecutaron **10 generaciones Klein y 2 comparaciones**, sin retries automáticos. Dos seguimientos diagnósticos dentro de la serie aislaron frase de encuadre y cardinalidad; se conservan los fallos iniciales. No hubo vídeo, descargas, nuevas dependencias, cambios de configuración persistida o promoción.

## Mediciones

Todos los casos devolvieron imagen válida e historial Comfy success sin OOM registrado. La aceptación visual es independiente del éxito técnico. Tiempos de solicitud completos; memoria global muestreada aproximadamente cada segundo en GPU de 12288 MiB.

| Caso | Resolución | Refs | Tiempo (s) | Pico / margen (MiB) | Resultado |
|---|---|---:|---:|---:|---|
| identity_style_512 | 512x512 | 2 | 22.187 | 11804 / 484 | Marco no solicitado: rechazo |
| identity_style_unframed_512 | 512x512 | 2 | 20.172 | 11737 / 551 | Sin marco; identidad/estilo visualmente conservados |
| identity_style_768 | 768x1376 | 2 | 28.266 | 11831 / 457 | Identidad conservada; estilo más sutil |
| style_identity_reversed_768 | 768x1376 | 2 | 28.281 | 11540 / 748 | Sin intercambio de roles observado |
| continuity_factual_768 | 768x1376 | 2 | 28.250 | 11901 / 387 | Taza/estado logrados; geometría de llave alterada |
| mpt_t2i_text_contract_768 | 768x1376 | 0 | 12.796 | 11692 / 596 | Sin texto; tres agujas en lugar de dos |
| mpt_temporal_hot_768 | 768x1376 | 1 | 21.235 | 11854 / 434 | Taza caliente con vapor visible |
| mpt_temporal_cooled_768 | 768x1376 | 1 | 19.453 | 11597 / 691 | Luz fría/sin gran penacho; QA temporal incierto |
| mpt_fallback_identity_style_seed43 | 768x1376 | 2 | 33.203 | 11574 / 714 | Fallback técnico funciona; duplica llave |
| mpt_explicit_quantity_seed43 | 768x1376 | 2 | 31.172 | 11625 / 663 | Cantidad explícita no corrige llave duplicada/fusionada |

Seed42 salvo las dos últimas (43); cuatro pasos y guidance1. Dos referencias repetidas a resolución objetivo, con orden invertido y nueva seed, sin fallo técnico, pero **con fallo semántico de repetibilidad**. Mínimo margen en esta serie:387MiB; el mínimo histórico325MiB sigue vigente. No son picos exactos ni memoria reservada/asignada por PyTorch. No se midió memoria por modelo; caches, cargas y otros procesos no están controlados.

La raíz temporal fue siempre la taza roja original; no se encadenó recursivamente la imagen caliente como nueva raíz para la fría. El estado visual cambió, pero no quedó certificado por el QA temporal. Roles explícitos y ordenados llegaron al bridge y los grafos Klein ejecutados coincidieron exactamente con los esperados. Ninguna inversión obligatoria de slots se deduce de un solo par: se conserva el orden del caller.

## Diagnóstico y decisiones

- **Prompt ambiguo:** “inside a square frame” añadió un marco físico. Cambiar solo la frase a fotografía cuadrada sin marco eliminó ese objeto. Evidencia causal de ese par, no regla especial por escena incorporada al código.
- **Texto inventado:** la cláusula breve de esfera limpia/sin marca/sin escritura eliminó la inscripción con seed42 frente al caso histórico. Apareció una tercera aguja. No se añadió una lista global de negativos ni se declaró resuelta la adherencia general.
- **Fidelidad factual:** Klein cambió la cabeza/dientes de una llave al trasladarla junto a la taza. El grafo recibió las referencias/prompt correctos; no se demostró fallo de bridge o MPT. Es una limitación observada del conjunto modelo/workflow en ese caso, sin atribuir una causa interna no medida.
- **Cardinalidad:** repetir identidad+estilo con seed43 duplicó/fusionó la llave. Explicitar exactamente una llave no lo corrigió. No continuar afinando ese prompt ni abrir tres referencias: falta estabilidad semántica con dos y el margen de memoria es pequeño.
- **QA:** el reloj con tres agujas obtuvo gross `status=pass`, pero `verdict=uncertain`, cobertura0,5. Florence incluso describió números que no se aprecian en la esfera. El QA basado en captions no acredita detalle fino. El estado frío obtuvo temporal `uncertain`, state_score0 y progression_score1: el caption omitía evidencia suficiente del estado. Ambos casos quedan sin aceptar.

## Integración y regresiones

[Contrato del caller](FLUX_KLEIN_4B_MPT_INTEGRATION.md): opt-in explícito, aliases4B separados de9B, calidad separada de conditioning, referencias/roles/descripciones ordenados, raíz y estado temporal, cuatro pasos/seed/tamaño efectivos, errores claros y metadata de procedencia. Un solo intento HTTP por generación experimental; sin fallback a9B.

Fallback técnico inicial conservador: solo ausencia de modelo/workflow confirmada por404. La prueba GPU inyectó esa respuesta primaria en el harness y ejecutó realmente Klein como secundario; **no fue una caída natural de Qwen**. Conservó ambas referencias y registró el modelo efectivo, pero produjo una imagen semánticamente rechazada. Prueba de transporte/caller, no certificación de calidad de fallback. OOM/5xx ambiguos y fallback semántico entre modelos siguen deshabilitados para este candidato.

El bucle de escenas rechaza candidatos Klein cuando el QA requerido no es un pass disponible y explícito. Temporal exige además pass temporal. Ausencia, desactivación o incertidumbre no permiten renderizar ni consolidar una raíz aceptada; tampoco disparan otro modelo ni retry semántico automático. El camino Qwen existente mantiene sus tests y comportamiento. Caller real y QA real ejecutados por separado; integración de gates en el bucle verificada offline. No atribuir un vídeo completo o una ejecución real planner→render a estas pruebas.

**241 tests + 2 subtests pasan**, incluidos42 casos nuevos. [Log final](validation/flux-klein-4b-mpt-regressions-2026-10-08.txt). Baseline de contratos/nativo:61pass. Nuevos tests:0–3refs, Standard/Precision independientes, orden, roles, descripción/exclusiones, seed/tamaño/pasos, raíz en segundo slot, contradicción temporal, alias T2I/Edit incompatible, assets/workflow ausentes, bridge fallido, tamaño incorrecto, transporte503 sin retry, fallback con pack completo, no fallback por QA/resultado ambiguo y rechazo real del bucle ante QA incierto. Los tests históricos no se modificaron.

## Comparación mínima

| Generador / caso | Pasos | Tiempo solicitud (s) | Pico global (MiB) | Observación |
|---|---:|---:|---:|---|
| Klein / reloj T2I |4|12,796|11692|Sin letras, pero tres agujas|
| Z-Image / mismo prompt T2I |8|35,891|11457|También tres agujas; sin letras apreciables|
| Klein / taza+llave, dos refs |4|28,250|11901|Llave con geometría alterada|
| Qwen2.1 / misma escena y referencias |20|140,062|11699|Llave visualmente más fiel; taza y vapor logrados|

Checkpoints efectivos confirmados en historial: Z-Image BF16 y Qwen2.1 int8_convrot, sin reinterpretar aliases. Qwen recibió exactamente dos inputs conectados a TextEncodeQwenImage21; un LoadImage placeholder adicional permanecía desconectado y no condicionó el output. Prompts finales adaptados al contrato propio de cada modelo y capturados. Una ejecución por comparación, distintas cargas/steps/caches: no declarar un ganador global ni extrapolar ventajas de latencia a warm/cold controlado. No se compararon exhaustivamente todas las capacidades.

## Rendimiento del pipeline

QA real:91,875s para el reloj y101,422s para comparación temporal, esta última incluye obtener el caption previo. En estos casos el coste de QA supera ampliamente la generación. No se midió un speedup del código añadido. Mejoras implementadas: fallo experimental de un intento, reutilización de referencias ya subidas, contrato temprano que evita dispatch inválido y comprobación de assets por tamaño/presencia tras hash de sesión, sin releer13GB por escena.

Siguiente optimización separada: obtener una sola descripción visual por candidato y reutilizarla para gates gross/temporal/factual; ejecutar rechazos de cantidad sustentados por caption antes del juicio LLM; evaluar un único juicio estructurado con las evidencias necesarias. Inspección detecta que gross llama primero al evaluador semántico (incluido LLM) antes de aplicar su regla barata de cantidad. No se cambió esa arquitectura en esta validación ni se sustituyó QA por un criterio más permisivo.

## Estado por capacidad y siguiente decisión

| Capacidad | Estado |
|---|---|
| T2I | Funcional a768×1376; adherencia factual/cantidad parcial |
| Edit / single-reference | Funcional; cambios de color/estado demostrados; no invariancia exacta |
| Multi-reference | Dos refs técnicamente repetibles; identidad+estilo funciona en casos, geometría/cantidad no fiable |
| Continuity | Raíz e identidad conservadas visualmente en los casos de taza; automatización aún gated |
| Temporal progression | Cambio visible ejecutado desde MPT; QA del estado frío incierto, no aceptación automática |
| Fallback | Contrato/offline y secundario GPU con fallo primario inyectado; no promovido |
| Standard / Precision automático | Pendiente selección por conditioning y admisión validada; defaults intactos |

**Candidato sigue planned.** Se detiene la ampliación de referencias y generación de vídeo ante estos fallos de admisión, sin ocultarlos con fallback. Siguiente experimento: validar evidencia visual de detalle/cantidad y estado temporal sobre los artifacts ya generados, sin nuevas generaciones; medir si una captura/juicio único conserva rechazo de errores y reduce el coste de QA. Después decidir una política explícita de routing por capacidad; no arreglarlo a base de más negativos ni cambiar automáticamente el encoder.

## Artifacts, cierre y trazabilidad

[Registro Klein](validation/flux-klein-4b-autonomous-2026-10-08.json), [comparación](validation/flux-klein-4b-comparison-2026-10-08.json). Requests, históriales, tiempos, muestras, hashes y paths de imágenes originales/normalizadas. Harnesses/specs/logs/imágenes locales en `local_image_stack/experiments/bridge/target/autonomous-2026-10-08`, ignorados por Git: conservar antes de archivar el worktree. Hashes de harness registrados; el harness evolucionó para añadir caller/fallback, las solicitudes exactas quedan por caso.

Cierre comprobado: cola vacía,8091 libre,8080health200,8090raíz404,8188stats200. Source externo del bridge mantiene los hashes previos; stable HEAD intacto. Binario Klein sin cambios. No se modificaron pesos, workflows, dependencias, servicios originales, Factory ni configuración persistida. El límite de revisión automática interrumpió un comando antes de ejecutarlo; se retomó tras el nuevo “sigue”, verificando que la última prueba no existía, sin duplicarla.

Checkpoint de implementación: `599a680ec17ca37b5e8cddc78d6d475d88e1858f`. El checkpoint posterior conserva evidencias y handoffs; identificar su SHA con Git.
