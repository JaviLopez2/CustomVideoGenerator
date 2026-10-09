# Handoff de auditoría de modelos — 2026-10-07

## Estado vigente — continuar autónomamente tras edición enmascarada, 2026-10-09

Base `f36b2a148b0725d387bb6c54e9eadef3ad5da4fa`, carpeta/rama/diez worktrees confirmados, status/diffs iniciales vacíos. [Ejecución y evidencia](MUG_MASKED_EDIT_EXECUTION.md): una solicitud12,328s,success,0 cambios RGB fuera/1213 dentro; unión inferior aún conectada y parche visible, cohorte cerrada inutilizable/0 retries/0 jueces. Preparación y resultados previos intactos; no inferir label negativo o fallo del juez. [Autonomía vigente](AUTONOMOUS_MPT_WORK_HANDOFF.md): objetivo persistente activo, seguir tareas y checkpoints sin pedir permiso rutinario. Próximo [plan offline](validation/mug-masked-no-reference-plan-2026-10-09.json) retira únicamente conditioning de referencia,1 generación/0 retries y decode crudo como diagnóstico; todavía sin ejecutar. Servicios compartidos conservados, assets rehashados; sin deps/modelos/routing/gates/workflows activos/estable modificados.112 tests de preparación históricos, checks frescos HTTP/historial/hash/píxeles/revisión. Conservar artifacts ignorados; SHA de cierre por Git/origin. Los pendientes anteriores son snapshots históricos.

## Estado vigente — preparación enmascarada completa, ejecución pendiente, 2026-10-09

Base publicada `903e68a1049e24e76c859fc1e2cce95488f39153`, carpeta/rama experimental confirmadas, status/diffs iniciales vacíos y diez worktrees. Se añaden `local_image_stack/experiments/klein4b_masked.py`, `test/test_klein4b_masked.py`, [informe de preparación](MUG_MASKED_EDIT_PREPARATION.md), grafo/protocolo/contratos y revisión de región por SHA. El constructor no despacha HTTP ni expone el payload legacy sin máscara. Modelos, conditioning, plantillas activas y bridge compilado anteriores intactos.

20 nodos/26 enlaces válidos contra 19 clases; fuente Comfy local fijada por SHA, sin importar torch ni ejecutar el VAE. Compatible a nivel de interfaces genéricas; aún no hay validación de tensores/GPU ni admisión de archivos. Máscara L512² binaria, 1215 blancos, bounds exclusivos `[323,335,360,374]`. Usuario: **«La zona cian es adecuada»**, [respuesta literal](validation/mug-masked-region-human-review-2026-10-09.json). Solo aprueba la región editable. Original rojo/azul intactos, control previo descartado y counts humanos positivos todavía pendientes.

**112 passed in 0.54s, Python exit0, sin warnings**, [log](validation/mug-masked-final-tests-2026-10-09.txt); 26 tests nuevos con RED/GREEN preservados. Avisos Pillow del GREEN inicial resueltos antes del test final. [Cierre](validation/mug-masked-closing-checks-2026-10-09.json) verifica bindings, reproducción del grafo, máscara, respuesta, JSON, scope y secrets sin mostrar valores. 0 nuevas generaciones/VLM/GPU/benchmarks/descargas/servicios iniciados o parados; sin cambios app/deps/modelos/gates/routing/workflows activos/estable. Conservar el directorio ignorado `target/mug-masked-preparation-2026-10-09` con máscara/SVG/PNG, además de originales y controles históricos. SHA de cierre por Git/origin, distinto de execution_base.

Siguiente tarea: ejecutar una sola edición enmascarada 512²/4 pasos/seed42/guidance1, cero retries. Revalidar pesos, input fuente, recursos y cola vacía; copiar solo `lower-contact-mask.png` a `MPT_MASKED_LOWER_CONTACT_20261009.png` en input Comfy con escalación específica y sin sobrescribir archivos distintos. Único POST directo a8188 con el grafo fijado; no iniciar8090/8091/8080. Timeout no cancela el job ni permite reenviar. Exigir cero cambios fuera de máscara y cambio dentro; después revisión humana del hueco inferior real/unión superior intacta. Solo con control válido y counts positivos revisados, preparar el plan real y hasta seis consultas actuales. Los snapshots siguientes conservan pendientes históricos, ya sustituidos por este estado.

## Estado vigente — control descartado por revisión humana, 2026-10-09

Base publicada `82f3496e1e560f5182f9b82e61f0cdd2cc116250`, misma carpeta/rama, status/diffs iniciales vacíos/diez worktrees, fetch0/0. Usuario: **«no se ve una separacion real.»**, sobre candidate e1725efb y board ae5904f1. [Respuesta literal/SHA](validation/mug-structural-control-human-review-2026-10-09.json), [protocolo](MUG_STRUCTURAL_CONTROL_PROTOCOL.md). Cohorte cerrada con negativo inutilizable;1 generación anterior consumida/0reintentos/0 consultas a jueces. No inferir label negativo, fallo de jueces, counts humanos de positivos o gold por píxel. Raw/artifacts y snapshot de revisión pendiente anterior intactos.

Siguiente tarea separada: preparar y verificar offline un grafo experimental de edición local con máscara; preservar superior y píxeles fuera de región, declarar1edit512²/4pasos/seed42/0retry, revisión humana antes de hasta6 consultas. Nodos de máscara/composición disponibles por GET actual; compatibilidad Klein/inpainting aún no probada. No se creó máscara/grafo/payload/imagen nueva ni cambió plantilla compilada. Usar pesos/deps existentes; si exige otros o cambiar servicios compartidos, parar por alcance. [Cierre](validation/mug-structural-control-human-review-closing-checks-2026-10-09.json) verifica JSON/respuesta/SHA/scope/diff/secret patterns; no unit tests nuevos por documentación,80 previos históricos.0 nueva generación/VLM/GPU/descarga/benchmark/servicios/app/modelos/gates/routing/deps/workflows/estable. Stable HEAD/tracked6d27ba4 confirmado por lectura; cierre SHA vía Git/origin.

## Estado vigente — edición estructural ejecutada, control aún no utilizable, 2026-10-09

Base publicada `ace19e77bc7d803067bbfb438cd6240de23097a3`, misma carpeta/rama confirmadas, status/diffs iniciales vacíos y diez worktrees. Usuario abrió8188. Una única edición fijada,512²/4pasos/seed42: HTTP200/PNG,14,127s; prompt_id dffb644f-29ce-4756-8bab-73397abd249c, Comfy success/completed sin execution_error. Resultado SHA e1725efb05ed662f6266aa07cf1322e4b2813e275628199141cebd446759610f. [Registro](validation/mug-structural-control-generation-2026-10-09.json), [protocolo actualizado](MUG_STRUCTURAL_CONTROL_PROTOCOL.md).

El asistente sigue viendo la unión inferior conectada; no hay corte inequívoco y el candidato no se etiqueta como negativo válido. [Inspección](validation/mug-structural-control-assistant-review-2026-10-09.json) separada de gold/revisión humana; pregunta pendiente sobre [tablero v2](D:/Apps/MPT-worktrees/image-model-routing-modernization/local_image_stack/experiments/bridge/target/mug-structural-control-generation-2026-10-09/review-board-v2.png), tres originales completos y detalle nearest entero2x. Ninguna consulta a jueces/reintento. No usar esta imagen como negativo a partir del prompt de edición ni atribuir su fallo a un juez.

Tres pesos rehashados, binario/workflows/fuentes iguales; referencia única creada en input de Comfy por escalación específica, sin sobrescribir ni cambiar originales. [Preflight actual](validation/mug-structural-control-generation-preflight-2026-10-09.json), [input](validation/mug-structural-control-input-2026-10-09.json). 8080/8091/8092 libres y cola0/0 antes; RAM libre~19,9GiB/VRAM libre~10,9GiB son snapshots previos globales, no picos por modelo. Bridge8091 propio cerrado/libre y cola0/0 después;8188 compartido conservado. 0 benchmarks/descargas/código/app/deps/modelos/gates/routing/workflows/estable. Las80 pruebas anteriores son históricas; pruebas actuales HTTP/historial/PNG/hashes/cierre, [verificación](validation/mug-structural-control-generation-closing-checks-2026-10-09.json).

Conservar target/mug-structural-control-generation-2026-10-09 ignorado: response original con base64, historial propio, log, resultado y dos tableros. V2 sustituye únicamente el doble resize del primer render por nearest directo2x; fuentes intactas. Esperar respuesta literal del usuario, preservar SHA. Si confirma unión intacta/ambigua, cerrar cohorte sin inferencia; un nuevo método/intento necesita presupuesto separado, no continuación automática de1 generación ya consumida. Si identifica hueco claro, inspeccionar/fijar sitios y registrar review antes del plan ejecutable. No actualizar el manifiesto de preparación con resultados inventados o habilitar producción. SHA de cierre por Git/origin.

## Estado vigente — control estructural de taza preparado, 2026-10-09

Base publicada `d765e58a76650b6b8410f141eeaecf61deda287f`, carpeta/rama experimental confirmadas, status/diffs iniciales vacíos, diez worktrees, fetch0/0. [Protocolo](MUG_STRUCTURAL_CONTROL_PROTOCOL.md) y [manifiesto](validation/mug-structural-control-protocol-2026-10-09.json) fijan rojo/azul positivos, una sola edición con unión inferior interrumpida (512²/4pasos/seed42),0reintentos, revisión humana previa y máximo6 consultas/3por candidato/perfil actual. [Request nativo listo](validation/mug-structural-control-edit-request-2026-10-09.json); no enviado. SHA/artifact negativo, revisión y plan de ejecución aún ausentes; no rellenar con placeholders ejecutables o etiquetas supuestas.

Preflight aislado: dos originales por SHA/tamaño,15 bindings de fuentes/perfil, dos payloads sin envío comparten prompt/schema y omiten metadata offline; Rust --dry-run exit0/dispatch false igual al grafo Python. Cuatro archivos de pesos presentes/tamaño esperado y runtime existe; no rehash completo ni readiness GPU. [Resultados](validation/mug-structural-control-preflight-2026-10-09.json), [log](validation/mug-structural-control-preflight-2026-10-09.txt). 80 tests actuales pasan,0,25s/exit0/sin warnings; comando en protocolo/[log](validation/mug-structural-control-tests-2026-10-09.txt), [cierre](validation/mug-structural-control-closing-checks-2026-10-09.json). No nuevos tests/código de implementación; 138 anteriores históricos. Fuente y hash local de texto pueden normalizar EOL al viajar por Git. Preservar grafo ignorado target/mug-structural-control-preparation-2026-10-09 y originales al archivar.

0 generación/VLM/GPU/descargas/inicio-parada de servicios/cambios app/modelos/gates/flags/routing/deps/workflows/estable. GET3s a11:30:52UTC:8080/8090/8188 no respondían. Solicitar apertura únicamente Comfy8188;8090 no requerido,8080 cerrado/GPU sin juego. Siguiente: revalidar assets/cola/puertos, crear control con bridge8091 propio, pedir revisión de imagen/sitios al usuario, fijar plan revisado y ejecutar luego jueces8092 propios uno a uno sin enviar el defecto al prompt. Si el control es ambiguo, parar la cohorte; no editar etiquetas o repetir automáticamente. Los jueces siguen diagnósticos. Stable/tracked protegido en6d27ba4 antes de esta fase; SHA final por Git/origin, distinto de execution_base.

## Estado vigente — localización offline de componentes, 2026-10-09

Base publicada `5c718730f1d94b0f5e90ab6a410966c0956e74a9`; mismo worktree/rama experimental, limpio al inicio. Nuevo auditor aislado y 24 tests; plan hash-pinned de cuatro raw, dos perfiles, v3 y ambas revisiones. 12 JSON originales revalidados y coverage idéntico, 8 observaciones positivas / 4 no aplicables, 14 relaciones disco/caja. [Informe](RETAINED_COMPONENT_SITES_REPORT.md), [plan](validation/retained-component-sites-plan-2026-10-09.json), [raw](validation/retained-component-sites-results-2026-10-09.json).

Qwen3.5 roja separa ambos contactos; azul solo alcanza disco superior por borde y deja inferior fuera. Qwen3-VL agrupa ambos sitios en una caja en cada taza. Ambos cubren el disco del centro del hueco, insuficiente para precisión de contorno. Margen 3px de dibujo no es confianza estadística ni tolerancia real certificada. No scores de identidad/correspondencias entre fotos, calibración o promoción. Fotos/raw/v3/juicios/revisiones intactos, B máscara completa excluida. 0 VLM/generaciones/descargas/GPU/servicios/cambios app/modelos/gates/flags/deps/routing/workflows/estable.

138 tests actuales pasan, 5,16 s, exit 0, sin warnings; RED24/GREEN24 conservados,124 previos históricos. [Cierre](validation/retained-component-sites-closing-checks-2026-10-09.json). Ocho SVG/PNG y tablero en target/retained-component-sites-2026-10-09, ignorados y preservables con anteriores assets. Bytes incrustados intactos, inspección del asistente separada de revisión humana. Render existente sin navegador/servidor o cambio por caché Fontconfig bloqueada. Fetch 0/0, stable/tracked intactos en 6d27ba4; SHA final por Git/origin, execution_head previo.

Siguiente tarea concreta: preparar protocolo mínimo de positivo rojo retenido y negativo estructural de unión del asa visiblemente interrumpida, con revisión/budget/criterios fijados antes de nueva edición o inferencia. Este checkpoint termina con la auditoría offline; la preparación del control estructural es la siguiente fase. Mantener pesos existentes y autoridad de diagnóstico. Ambos jueces siguen diagnósticos; no pedir de nuevo A/B/C ni ajustar prompts para forzar passes en estos raw.

## Estado vigente — prueba acotada de componentes y perspectiva, 2026-10-09

Base publicada `19c660b9aff0e5b7f17159c4701ce91838df920e`; mismo worktree/rama, inicialmente limpio. Script experimental y 19 tests nuevos, plan fijado con hashes de script/anotación/revisiones. 33 controles sintéticos/66 ajustes completados, sin inferencias/generaciones/GPU/servicios. Auditoría de cuatro pares retenidos: roles nominales compartidos C6/A5/B0/tazas6, sin correspondencia física certificada ni cálculo geométrico sobre fotos. [Informe](COMPONENT_POSE_LIMITS_REPORT.md), [plan](validation/component-pose-plan-2026-10-09.json), [raw](validation/component-pose-results-2026-10-09.json).

Similitud confunde inclinación planar con discrepancia; homografía del plano no corrige puntos a distinta profundidad. Cuatro anclajes deformados pueden encajar sin validación independiente; cotas de incertidumbre supuestas se solapan en cambio pequeño. Es geometría sintética medida localmente, no pose recuperada de fotos ni calibración de identidad. B mantiene juicio humano de cambio total y máscara discutida/excluida; v3, A/B/C y ambas respuestas humanas intactos. No admisión o promoción; app/defaults/flags/gates/routing/modelos/deps/workflows/estable sin cambios.

124 tests actuales pasan, 1 warning esperado, 8,86s/exit0; RED19/GREEN19 preservados, suite anterior105 histórica. [Cierre](validation/component-pose-closing-checks-2026-10-09.json). Diagrama SVG/PNG inspeccionado en target/component-pose-limits-2026-10-09, ignorado y preservable junto a anteriores assets. Node/sharp existente, sin navegador/servidor ni cambios por caché Fontconfig restringida. Fetch0/0, stable/tracked intactos en6d27ba4; checkpoint final por historial/origin, execution_head previo.

Siguiente tarea concreta: auditoría de localización de los raw guardados isolated-mug-hole/contacts-qwen35/qwen3vl, sobre roja/azul y sitios aproximadamente revisados con margen±3px. Comparar dentro de cada imagen, conservar agregación/omisión, sin repetir inferencias ni tratar cobertura puntual como contorno/identidad. No abrir servicios para ello. Negativo estructural de taza y umbrales calibrados siguen pendientes; no nuevos pesos, generación o promoción implícitos.

## Estado vigente — borradores espaciales y dos revisiones humanas, 2026-10-09

Base publicada `03c36ba788090f8e904d5d7b49200e543cf98f8c`, mismo worktree/rama experimental. Se conservaron los borradores uncommitted al reanudar. Se añaden renderer/validador aislado, 16 tests, tres versiones de contornos, reportes/logs y dos respuestas humanas literales vinculadas a anotación/tablero SHA. Seis contornos, tres huecos, 36 puntos; originales y A/B/C intactos. [Informe y límites](SPATIAL_ANNOTATION_REVIEW_REPORT.md), [v3](validation/spatial-annotation-draft-v3-2026-10-09.json), [última revisión](validation/spatial-annotation-human-review-v3-2026-10-09.json).

V3 redibuja B, anillos de A y borde izquierdo de las tazas, preserva todos los puntos/huecos y ambas primeras imágenes. B aún incorpora sombra según el usuario y su perspectiva dificulta el borde: máscara completa discutida y excluida de identidad/calibración. Puntos parecen coincidir y huecos de taza coinciden aproximadamente según la primera revisión; eso no certifica píxeles o correspondencia física. Sin comentarios adicionales no se aprueban otros contornos automáticamente. 0 scores/VLM/generaciones/descargas/benchmarksGPU/servicios ni cambios app/gates/flags/modelos/routing/deps/workflows/estable.

105 tests actuales pasan con 1 warning esperado,6,06 s, exit 0; logs RED/GREEN y ejecución anterior separados. Guardas de procedencia verificadas. [Cierre](validation/spatial-annotation-closing-checks-2026-10-09.json). SVG/PNG estáticos comprobados/visualizados; HTML generado sin validación de interacción porque navegador bloquea file://, sin workaround. Guardar todos los target/spatial-annotation-* ignorados, snapshot inicial del renderer y originales al archivar. Fetch 0/0; stable/tracked protegido en 6d27ba4. SHA de cierre por Git/origin, no execution_head del report.

Siguiente tarea concreta: protocolo de componentes/pose con incertidumbre explícita, manteniendo B fuera de mediciones de máscara completa hasta resolver metal/sombra. No pedir otra vez los juicios globales A/B/C, no convertir inspección aproximada en gold, ni calibrar sin correspondencias/tolerancias y negativo estructural de taza revisado. No hace falta abrir servicios para este checkpoint; no hay nueva autorización de pesos, generación o promoción.

## Estado vigente — auditoría espacial independiente, 2026-10-09

Base publicada `0e4a0aa`; mismo worktree/rama experimental, inicialmente limpio. Auditado CPU SIFT full/ROI±8 y HSV S0,15/0,25/0,35 sobre6 retenciones,7 comparaciones. C/recolor tienen registro local; A y B no encajan en ROI y máscaras incompletas invierten scores: no gate de forma/identidad. Todos uncertain/unavailable, sin aprobación/rechazo. [Informe](SPATIAL_GEOMETRY_AUDIT_REPORT.md), [raw](validation/spatial-geometry-audit-results-2026-10-09.json), [análisis](validation/spatial-geometry-audit-analysis-2026-10-09.json).0VLM/generaciones/descargas/benchmarksGPU/servicios iniciados.

Nuevos: scripts/audit_spatial_geometry.py, test/test_spatial_geometry_audit.py, dos planes hash-pinned, capacidades, raw, análisis, logs/closing. App/modelos/routing/gates/flags/deps/workflows/estable intactos. Error de sintaxis y fallo API FailedEstimation retenidos; corrección bool(model) con regresión real RED→GREEN, parámetros iguales.89tests actuales pasan exit0,1warning esperado; suites previas históricas.4SVG locales ignorados con bytes originales intactos; conservar al archivar. Fetch0/0 tras escalación específica para metadata Git; stable/tracked protegido en6d27ba4. Checkpoint final por historial/origin, distinto de execution_head del raw.

Pendiente: anotar objeto completo y landmarks de componentes con overlays y procedencia explícita; revisión independiente antes de tratar anotaciones como gold. Declarar pose/proyección permitidas y sumar negativos estructurales revisados antes de calibrar. No retocar prompts/parámetros para forzar pass, descargar pesos nuevos o activar gates/vídeo automáticamente. No intervención del usuario necesaria para cerrar esta auditoría; no se solicitan de nuevo sus juicios A/B/C.

## Estado vigente — componentes aislados, 2026-10-08

Desde `3e2b873`, 20 controles retenidos sobre un componente por request, ambos modelos disponibles. Formato completo sin timeouts/truncaciones; hueco del asa mejora, contactos y bandas siguen agrupados/inconsistentes y B no se prioriza. 0generaciones/retries/descargas, código/app/routing/gates/flags/deps/workflows sin cambios. Nuevos perfiles, raw, análisis/replays,20SVG locales y revisión del asistente separada de A/B/C. [Informe](ISOLATED_COMPONENTS_REPORT.md).

96 tests enfocados actuales pasan, exit0,3,66s; suite520+17 previa es histórica sobre el mismo código, no ejecución nueva. Stable/tracked intactos, seis servidores propios cerrados. Pendiente concreto: auditar verificación espacial independiente de forma/localización sobre retenciones antes de admisión o vídeo completo. No ampliar budget ni reinterpretar prosa como pass. Handoff/checkpoint finales por historial/origin; fases siguientes históricas.

## Estado vigente — ubicaciones y candidatos, 2026-10-08

Desde checkpoint publicado `fe63c61`, protocolo experimental de boxes normalizadas y overlays/replay offline. 5 nuevas inferencias sobre artifacts existentes (16 en esta continuación), 0 generaciones. Qwen3.5 separa contactos pero desplaza regiones y trunca azul; Qwen3-VL completa3 controles pero niega hueco del asa y agrega contactos. Ninguno habilitado para identidad/admisión. Solo harness/diagnóstico opt-in; no nuevo wiring, config, modelo, deps, workflows o routing. [Informe y pendiente](VISUAL_LOCATION_DIAGNOSTICS_REPORT.md).

520 tests +17 subtests pasan, 1 integración omitida, exit0, 17,04s. Raw/hash/human labels preservados, servidores propios cerrados y stable/tracked intactos. Próximo control: componentes por request y revisión independiente de regiones; no forzar QA pass, descargar otro candidato o ejecutar vídeo sin alcance específico. SHA final por Git/origin, no base de ejecución. Las fases siguientes son históricas.

## Estado vigente — diagnóstico visual experimental, 2026-10-08

Continuación desde `7c1871c` en el mismo worktree/rama experimental. Contraste controlado del formato y cuatro llaves: 11 inferencias sobre artifacts existentes, 0 generaciones. Prompt explícito mejora JSON, pero el modelo agrega ubicaciones y no señala el defecto B revisado por el usuario; no certifica geometría/identidad. Added offline diagnostic adapter and explicit private caller injection, default None; sin wiring automático, flags, decisiones QA, routing, modelos, deps o workflows. [Informe y comandos](COMPONENT_DECODING_DIAGNOSTICS_REPORT.md).

495 tests +17 subtests pasan, 1 integración omitida, exit 0, 18,70s. Raw failures/hashes/human annotations preservados; cinco servidores 8092 propios cerrados. Stable protegido `6d27ba4963ffe469d635db71eaeec506a8ff4b61`, tracked intacto. Checkpoint de cierre mediante historial/origin; la base de ejecución no es el SHA final. Pendiente concreto: evidencia de ubicaciones con coordenadas y revisión offline antes de admisión o vídeo completo. No afirmar que investigación/código histórico ya validan esa capacidad. Las secciones históricas siguientes conservan su procedencia.

## Procedencia y alcance

Documentos reconstruidos en Windows por autorización explícita del usuario. El agente remoto, según informa el usuario, los había creado en `ab8e483` local y no los publicó. No se recuperó ese objeto ni se presentó su investigación como completada. La auditoría de esta sesión parte del código e historial realmente disponibles.

Worktree: `D:\Apps\MPT-worktrees\image-model-routing-modernization`. Rama: `factory/image-model-routing-modernization`. Base de código: `7b2c303196fe16f9844a9ba3f081e8f296bc1dd9`. Preparación publicada: `e759b39072bb32959ad06d86106c21f7da3b117a`. El commit documental que contiene este archivo es el checkpoint de cierre, identificable con `git log -1 --format=%H -- docs/IMAGE_MODEL_ROUTING_HANDOFF.md`; no confundirlo con la base.

## Trabajo realizado

- HEAD/status/diff/handoffs comprobados. Fetch de origin: sin divergencia; se conservó el checkpoint de preparación.
- Revisión por patrones de secretos en `AGENTS.md` y el handoff local antes de publicar. El primer push falló por credenciales; el usuario autorizó Git Credential Manager y completó login en navegador. El siguiente fetch/push publicó `e759b39` sin force-push. No se guardaron credenciales en el proyecto.
- Se documentaron las fases de código ya existentes: fixes de outputs/estado temporal, Precision sin referencias y deduplicación, con sus commits y tests. No se reimplementaron ni se lanzaron sus pruebas históricas.
- Se contrastaron configuración local seleccionada, funciones de routing/payload/perfil y fuente del bridge, workflows en disco, nodos/asset lists vivos y capacidad GPU. No se cargó ningún modelo por estas comprobaciones.
- Se consultaron fuentes oficiales actuales para baseline y selección de candidatos. Fuentes, hechos publicados, observaciones y estimaciones separados en [RND](IMAGE_MODEL_ROUTING_RND.md).

## Hallazgos que condicionan la continuación

1. Standard Z Turbo, Precision Qwen 2.1 y fallback Klein son aliases concretos, no garantías de capacidad intercambiable. Las promociones de continuidad y fallback alteran la ruta efectiva.
2. Balanced Qwen usa `768x1376`, 20 pasos y un candidato por precedencia de perfil; el template aislado y los ajustes genéricos no describen toda ejecución.
3. `flux-klein-precision` referencia Klein **9B KV** y no tiene disponibles en los loaders vivos `qwen_3_8b_fp8mixed.safetensors` ni `flux2-vae.safetensors`. No se reparó; la plantilla cargada por el proceso bridge sigue sin verificar.
4. Qwen 2.1 tiene licencia de investigación; Klein 9B tiene licencia no comercial del modelo. Klein 4B, Z Turbo/Base y Qwen Edit 2511 declaran Apache 2.0 para sus modelos. Revisar cada componente concreto antes de adopción. Las condiciones de outputs y las del uso del modelo son distintas.
5. Klein 4B destilado es el primer candidato documental propuesto; no está adoptado ni validado en esta 3060. Las cifras oficiales de memoria de BFL varían según fuente y no permiten garantizar el pico local.
6. La igualdad del workflow Qwen local con el externo se comprobó como JSON, no por bytes. Todos los nodos de los tres workflows están registrados; ese dato no prueba que los tres puedan ejecutar con los assets disponibles.

## Verificación y límites

Evidencia local y comprobaciones documentales: [registro JSON](validation/image-model-routing-audit-2026-10-07.json). Revisión final de scope, secretos por patrones, referencias locales, commits citados y `git diff --check`. No se ejecutaron tests de aplicación porque solo se modifica documentación; no hay nueva certificación funcional.

Sin cambios de producción, modelos, dependencias, workflows o servicios; sin descargas de pesos, generación, benchmarks, force-push, merge ni publicación de vídeos. La copia estable y las demás ramas no se modificaron. La ocupación GPU leída es un snapshot global, no un perfil de inferencia.

## Siguiente tarea

Preparar únicamente el plan de integración aislada de Klein 4B destilado: variantes/aliases, manifiesto de pesos y licencias, diferencias respecto a Klein 9B KV, payloads T2I/edit/continuidad, condiciones de fallback, tests offline y criterios de aceptación. Incorporar el diagnóstico del fallback actual y aclarar el destino comercial o de investigación antes de recomendar un despliegue. Toda instalación, edición de producción/workflows, descarga o prueba GPU necesita un nuevo encargo específico.

Si se aporta `ab8e483`, reconciliar sus conclusiones sin reemplazar automáticamente este historial. Para continuar, confirmar branch/HEAD/status y volver a hacer fetch; conservar cualquier nuevo cambio válido.

## Checkpoint posterior: aliases, manifiesto y tests offline

Base de esta implementación: `37ef653e8d47483e997d6b8fb52ebc1a5ba1732d`, worktree limpio y sincronizado al comenzar. El nuevo texto del usuario concreta el experimento 4B Distilled FP8, con aliases separados y máximo tres referencias. Se implementó un módulo sin imports de producción, clientes HTTP, descarga o dispatch; no se modificaron `app/`, dependencias, configuración local, bridge ni workflows activos.

Archivos principales: `local_image_stack/experiments/klein4b.py`, `test/test_klein4b_experiment.py`, `docs/validation/flux-klein-4b-assets.json` y [plan experimental](FLUX_KLEIN_4B_EXPERIMENT.md). El manifiesto queda `planned` y los payloads `dispatch_allowed=false`. Los templates oficiales UI están referenciados; la conversión API y la adaptación al bridge no están completadas.

Validación: 25 tests nuevos pasan; la suite enfocada conjunta termina con 112 passed. La suite adicional de continuidad da 14 passed y 1 failed: una aserción exige `same glyph on the tile`, pero el prompt comienza con `Same glyph on the tile`. Los archivos del fallo son idénticos a la base según `git diff --exit-code`; no se parchearon tests existentes ni producción. Logs en `docs/validation/flux-klein-4b-*-2026-10-07.txt`. Este fallo impide declarar todo el gate de regresiones aprobado. La preparación de payloads y la admisión con fixtures sintéticas no certifican ejecución GPU.

Siguiente tarea: exportar/revisar grafos API aislados y reconciliar slots, roles y parámetros Flux con el bridge, sin instalar ni generar. Resolver la regresión preexistente mediante una tarea acotada antes de promoción. Los pasos GPU y la activación productiva siguen pendientes de autorización específica. El SHA del checkpoint que contiene este bloque se obtiene del historial de este archivo; no sustituye el SHA base.

## Checkpoint posterior: grafos API y adaptación offline

Base: `d4d32c4bedce37b1d0bbc214a63e736d9b11e4f9`. Worktree limpio al comenzar, fetch sin divergencia (`0 0`). Se prepararon dos grafos API nativos aislados en `local_image_stack/experiments/workflows/`, hashes de archivos locales y de templates upstream en el manifiesto, aviso MIT y regla LF para conservar bytes. Reconstrucción de topología oficial, no exportación desde UI. No se tocó el workflow 9B activo.

Nuevo `klein4b_graph.prepare_graph`: verificación de plantilla, bindings de prompt/seed/dimensiones/steps/CFG y expansión ordenada de bloques para 1–3 referencias en ambos conditionings. Títulos `Subject Reference N` compatibles con filenames del bridge; roles en prompt. No uploads, HTTP ni dispatch. El Rust actual no materializa esos bloques ni consume pasos/CFG Flux del payload; integrar este adaptador con el servicio sigue pendiente. Ver [detalle](FLUX_KLEIN_4B_EXPERIMENT.md).

Tests: **126 passed**, log `validation/flux-klein-4b-api-tests-2026-10-07.txt`. Se acotó una aserción del test experimental que confundía `9b` hexadecimal dentro de un hash con un checkpoint 9B. Tests Qwen/continuidad existentes intactos. Suite adicional: **14 passed, 1 failed**, mismo fallo de capitalización, log `validation/flux-klein-4b-api-continuity-2026-10-07.txt`; gate global no aprobado. Diff contra base de `app/`, `test/services/`, bridge y workflows activos vacío.

Esquemas vivos comprobados mediante GET, sin POST: clases/campos/enlaces compatibles, sin certificar ejecutabilidad ni existencia de inputs. Evidencia `validation/flux-klein-4b-api-schema-2026-10-07.json`: DiT/VAE no listados, encoder listado sin hash; placeholder Edit requiere input real. Revisiones de ejecución y hashes de pesos siguen nulos, estado `planned`. Sin descargas de pesos, cambios de dependencias, servicios, generaciones, benchmarks o producción.

Siguiente tarea concreta: diagnosticar y acordar corrección del gate histórico de continuidad sin debilitar QA; su modificación no se hizo porque el plan exige conservar los tests actuales de Qwen/continuidad. Luego, con autorización específica, verificar encoder disponible y planificar assets/prueba mínima GPU. No promover ni activar aliases por este checkpoint. El SHA de cierre se identifica con `git log -1 --format=%H -- docs/IMAGE_MODEL_ROUTING_HANDOFF.md`.

## Checkpoint posterior: cierre del gate de continuidad

Base `de118682e296355dd8d5abf4a25030b7c9b6968d`, misma rama/worktree experimental, limpio y sincronizado al comenzar (`0 0` tras fetch). El usuario autorizó continuar con la siguiente tarea de resolver el gate. Historial: `f7f4c71c216844b7d1761788fc90939cea67882e` introdujo `_same_continuity_subject` para eliminar `The same same`; al capitalizar un prefijo `same`, dejó de conservar el fragmento `same glyph on the tile` que exige el test histórico.

Corrección mínima en `app/services/llm.py` de este worktree: normalizar únicamente el prefijo inicial `same` o `the same` (sin distinguir mayúsculas) a `The same`, conservando intacto el resto de la identidad. Mantiene la deduplicación y no altera routing, elección de raíces, estados temporales, fallback ni QA. No se modificó ningún archivo de `test/services/`; los tests existentes se conservan. Nuevo `test/test_continuity_phrase.py`: diez casos del planner con LLM simulado, cubriendo casing del prefijo, nombres propios, ausencia de IDs internos y estado temporal.

Validación real en Python MPT portable, integración/GPU deshabilitadas y Hugging Face offline: **25 passed** en los casos nuevos + gate histórico ([log](validation/continuity-prefix-focused-2026-10-07.txt)); **151 passed** en la validación ampliada con contratos Klein y suites Qwen/continuidad/fallback ([log](validation/continuity-prefix-regressions-2026-10-07.txt)). El fallo histórico queda resuelto para estas suites; no se afirma haber ejecutado todos los tests del repositorio. Los logs de fallos previos se conservan como evidencia histórica.

Revisión de diff, sintaxis, enlaces y patrones de secretos antes de publicar. Cambio del planner solo en la rama experimental, sin desplegarlo ni modificar la copia estable. No hay cambios de pesos, dependencias, manifiesto de assets, grafos, bridge o servicios, ni descargas/generaciones/benchmarks. Klein sigue `planned`; pasar este gate no acredita memoria ni calidad GPU.

Siguiente tarea concreta: verificar procedencia e identidad del encoder ya disponible mediante lectura/hash y preparar un plan de instalación de los dos assets faltantes. Toda descarga, ejecución GPU o activación del bridge necesita autorización específica. El checkpoint que contiene este bloque se identifica con el historial de este archivo; no confundirlo con el SHA base.

## Checkpoint posterior: preflight de assets

Base `57a5747016c1c4b4109860cb0b696edab9eabc75`, worktree limpio y fetch sin divergencia. Se leyó íntegramente el encoder local y se contrastaron SHA-256/tamaño con metadatos LFS públicos de Comfy-Org/z_image_turbo, revisión fijada. Coinciden: **8.044.982.048 bytes**, SHA-256 `6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a`. Cabecera válida para los checks estructurales realizados: 398 tensores BF16, offsets contiguos; no se importó Torch ni se cargó el modelo. No se certifica su historia original de instalación ni ejecución.

Manifiesto: encoder `verified_local_bytes`; DiT/VAE `not_downloaded`, SHA local nulo, SHA esperado/tamaño/revisión upstream fijados. VAE Comfy tiene el mismo LFS que el archivo Diffusers del autoencoder BFL; licencia de componente distinguida del repositorio dev. Evidencia [JSON](validation/flux-klein-4b-asset-preflight-2026-10-07.json). Plan concreto de descarga parcial/verificación/destinos y fases posteriores en [INSTALL_PLAN](FLUX_KLEIN_4B_INSTALL_PLAN.md). Faltan **4.406.838.076 bytes** (4,41 GB); C tiene unos 135 GB libres en este snapshot. No es una estimación de VRAM.

Tests afectados: **39 passed**, [log](validation/flux-klein-4b-asset-preflight-tests-2026-10-07.txt). Se actualizó únicamente la aserción experimental de aislamiento para reflejar el encoder verificado con candidato aún `planned`; tests históricos y aplicación intactos. Revisión final de JSON/diff/hashes/enlaces/secretos antes de publicar. Los 151 tests del checkpoint anterior no se repitieron porque no cambió el código de aplicación.

Sin escrituras en ComfyUI/Factory/estable ni cambios de servicios, dependencias, modelos, bridge, routing o grafos; no se descargaron binarios ni se ejecutó generación/GPU. Siguiente acción que requiere autorización específica: descargar/verificar solo DiT y VAE en los destinos detallados del plan, conservando el encoder existente. Esa autorización no incluiría activar aliases, reiniciar ni ejecutar GPU. El SHA de cierre se obtiene del historial de este archivo.

## Checkpoint posterior: instalación autorizada de DiT/VAE

Base `99d6abddf6ea525f040ac1d0d881f88184950bef`, worktree limpio, fetch sin divergencia. El usuario autorizó descargar/verificar DiT y VAE y considerar otro encoder si fuese mejor. Se conservó el encoder oficial Qwen3-4B BF16 verificado: faltan mediciones que justifiquen sustituirlo. No se descargó una variante alternativa ni se reemplazó un archivo previo.

Instalados 4.406.838.076 bytes en ComfyUI: `models\diffusion_models\flux-2-klein-4b-fp8.safetensors` y `models\vae\flux2-vae.safetensors`. Descargas desde revisiones fijadas, parciales creados sin sobrescritura y renombrados después de validar tamaño/SHA/cabecera. Encoder rehashado y sin cambios. Manifiesto registra los tres hashes locales y evidencia; sigue `planned`, con revisiones de ejecución nulas. [Registro](validation/flux-klein-4b-install-2026-10-07.json) y [plan/resultado](FLUX_KLEIN_4B_INSTALL_PLAN.md).

GET posterior `/object_info`: conexión rechazada en 8188 (WinError 10061), sin intento de inicio/reinicio. No afirmar que el servicio ha listado/cargado los nuevos modelos. Contratos afectados: **39 passed**, [log](validation/flux-klein-4b-install-tests-2026-10-07.txt). Test experimental de aislamiento actualizado para assets verificados con candidato no listo; tests históricos/código de aplicación/grafos/bridge intactos. Sin generación/GPU, cambios de dependencias, publicación o promoción. Stable HEAD sigue `6d27ba4963ffe469d635db71eaeec506a8ff4b61`.

Siguiente tarea: preparar integración experimental del bridge y recuperar servicio/inventario. Inicio/reinicio de ComfyUI y ejecución GPU no estaban incluidos en esta autorización; deben encargarse específicamente. No modificar fallback ni alias 9B, ni instalar aliases en el servicio activo por iniciativa propia. Identificar el checkpoint de cierre en el historial de este archivo.

### Revalidación de servicios tras el checkpoint de instalación

Instalación publicada en `b3e11915f8099c0888c5c87bff05c2b71c0b8306`. Tras la oferta del usuario de abrir servidores, un nuevo GET confirma ComfyUI 8188 HTTP 200 y los tres assets listados; bridge 8090 raíz HTTP 404 (liveness, no certificación de generación); MPT 8080 health HTTP 200. La conexión rechazada anterior queda como evento histórico, no como bloqueo vigente. Evidencia añadida al registro de instalación. El agente no inició/reinició servicios ni envió POST o generaciones.

Siguiente tarea vigente: integración experimental del bridge; después prueba GPU mínima con autorización específica. Inventario y hashes están verificados, pero revisiones de ejecución/inferencia y gates de memoria/calidad siguen pendientes; candidato `planned`. Esta revalidación solo modifica documentación/metadatos, sin nuevos tests funcionales ni cambios de código.

## Checkpoint posterior: integración nativa experimental del bridge

Base `f38c63e001796dab514e192a2b06aa30b479f9f8`, misma rama/worktree limpio y fetch sin divergencia. Se inspeccionó el checkout externo: HEAD `9419883c954de0e7c15d9d3ba16deca850d8605f`, con cambios locales Qwen/bridge conservados. Snapshot previo `comfyui.rs` igual al source externo normalizado; hashes de esos archivos no cambiaron durante la tarea. No se escribió en `D:\Comfyui2Openai`.

Nuevo crate aislado `local_image_stack/experiments/bridge`, con lockfile existente, MIT upstream, main experimental, materializador Rust y feature `klein4b_experiment`. Reutiliza snapshots locales de comfyui/proxy y añade ws.rs faltante. Hook en snapshot local `comfyui.rs`: solo aliases 4B, binding validado/expandido antes del parche legacy; no sustituye la ruta legacy ni el proceso 8090. Carga únicamente dos plantillas experimentales y exige igualdad JSON con sus copias compiladas. [Contrato, comandos y modos](../local_image_stack/experiments/bridge/README.md).

Native Rust: T2I cero refs, Edit 1–3 refs ordenadas/roles explícitos, cadenas ReferenceLatent positivas y negativas, seed/tamaño/batch/4 pasos/CFG 1. Rechaza aliases legacy en esta instancia, refs ausentes/duplicadas/absolutas, slots extra y contratos temporales explícitos contradictorios. Agrega rol/raíz/estado solicitado sin duplicar cláusulas del builder Python. No modifica fallback/QA ni routing MPT.

Build offline/locked y prueba Rust legacy: **1 passed**. Suite ampliada Python: **173 passed**, incluidos 22 casos del binario/HTTP. Logs [build](validation/flux-klein-4b-bridge-build-2026-10-07.txt), [Rust](validation/flux-klein-4b-bridge-rust-tests-2026-10-07.txt), [regresiones finales](validation/flux-klein-4b-bridge-regressions-2026-10-07.txt). Seis warnings dead_code heredados del snapshot WS sin uso. Tests históricos de Qwen/continuidad intactos. [Procedencia, hashes y límites](validation/flux-klein-4b-bridge-provenance-2026-10-07.json).

HTTP preview efímero en 8091: aliases listados, transformación correcta y generación bloqueada 403; proceso de prueba cerrado y puerto liberado. No hubo POST a Comfy ni GPU. `--serve-gpu` está implementado para futura activación específica, pero no se ejecutó. Servicios originales siguen respondiendo 8080 health 200, 8090 raíz 404, 8188 system_stats 200. Binario/target ignorados; no depende de un cambio global de librerías.

Siguiente tarea concreta: prueba GPU mínima T2I con autorización específica, usando esta instancia aislada y parámetros pequeños; revalidar assets/inventario, fijar identidad del binario en ejecución y medir OOM/VRAM/tiempo. Después single-ref/temporal/multi-ref y caller MPT experimental con roles/endpoint 8091. No cambiar configuración estable ni asumir que el caller actual manda reference_roles. El candidato sigue `planned`; SHA del checkpoint de cierre en el historial de este archivo.

## Checkpoint posterior: una prueba GPU T2I autorizada

Base `066fcdddfdc86d5dcae5718d3b3baadbab769cdd`, worktree limpio y fetch sin divergencia. El usuario autorizó la única generación propuesta: T2I 512×512, 4 pasos, seed 42. Assets y binario rehashados, cola vacía revalidada; una sola solicitud a la instancia experimental 8091 `--serve-gpu`, sin reintentos.

**PASS de ese caso mínimo**: bridge HTTP 200, una imagen PNG 512×512, historial Comfy `success`, sin errores registrados. Tiempo completo 10,109 s; execution_start→execution_success 8,672 s. VRAM global baseline 4424 MiB; pico muestreado 11433 MiB/12288, 10 muestras a intervalo objetivo 1 s, margen observado 855 MiB. No es memoria por modelo ni pico exacto; caches/otros procesos no controlados. Encoder BF16 conservado. [Resultado y límites](FLUX_KLEIN_4B_GPU_SMOKE.md), [registro JSON](validation/flux-klein-4b-gpu-smoke-512-seed42-2026-10-07.json).

PNG inspeccionado: una taza roja completa sobre mesa junto a ventana, sin texto/watermark apreciable. SHA de imagen devuelta igual al original Comfy. Paths absolutos de ambas copias en el registro; artifacts locales bajo target ignorados por Git, conservar antes de archivar el worktree. No se certifica calidad comparativa/identidad/temporal ni repetibilidad por esta única imagen.

Bridge experimental cerrado, 8091 libre; servicios originales vivos y stable HEAD `6d27ba4963ffe469d635db71eaeec506a8ff4b61` intacto. Sin cambios de routing/QA/fallback/configuración/dependencias, nuevas descargas, reinicios o publicación. Runtime Comfy reportado 0.37.0/Python3.13.12/Torch2.12.1+cu130; source HEAD observado no certifica revisión cargada. No se marca candidato `ready`.

Siguiente tarea concreta propuesta: una edición single-ref 512×512 con esta taza y cambio visible, previa autorización específica de otra generación. Luego temporal/multi-ref/resolución objetivo y caller MPT/smoke de dos escenas. La autorización actual quedó consumida en una solicitud; no seguir generando. Los tests históricos no se repitieron porque solo cambian documentos/evidencia; las verificaciones runtime realizadas están registradas.

## Checkpoint posterior: single-reference edit

Base `a3d82a25e16ed301ed79f20ca0eb7c5bb357a34b`, worktree limpio. Tras petición de siguiente prueba y turno interrumpido, se confirmó ausencia de artifacts de edición, cola vacía y 8091 libre. Una única solicitud edit512×512/4 pasos/seed42, referencia propia de la taza roja con rol identity_reference, cambio pedido rojo→azul profundo conservando geometría/escena. Input copiado sin sobrescritura; assets/binario rehashados. No reintentos.

**PASS técnico y visual informal del caso**: HTTP200, PNG512×512, historial success sin errores, color azul observado con forma/asa/encuadre/fondo bien conservados a simple vista. Tiempo solicitud14,219s; job13,926s. Baseline global4264MiB; pico muestreado11756/12288MiB, 14 muestras, margen532MiB. Referencia escalada a1MP por el grafo existente; no se cambió workflow. Caches/otros procesos no controlados, sin medida por modelo ni invariancia geométrica exacta. [Resultado](FLUX_KLEIN_4B_SINGLE_REF_SMOKE.md), [registro](validation/flux-klein-4b-gpu-single-ref-512-seed42-2026-10-07.json).

Artifact original/copia/request/logs con paths y hashes registrados; no subir binarios a Git y preservar antes de archivar. Bridge experimental cerrado/puerto libre, cola final vacía, servicios originales responden y estable intacto. No hay cambios de código, dependencias, configuración, routing/QA/fallback ni publicación; candidato `planned`. Tests de código no repetidos, runtime/documentación verificados.

El usuario preguntó por una prueba más compleja durante la ejecución: se respondió que conviene después de este gate y no se lanzó otra generación. Siguiente propuesta: un caso de continuidad con raíz original, misma taza/mesa/ventana, cambio visible a luz de atardecer y vapor, conservando identidad y encuadre; requiere nueva autorización. Luego multi-ref/resolución objetivo y MPT aislado. No considerar completadas esas fases.

## Checkpoint posterior: continuidad y detalle a resolución objetivo

Base `6ba2402da916925e1334ba31e68b4fb6cf486cf8`. Encargo explícito de seguir probando resolución/detalles: tres solicitudes anunciadas y ejecutadas, sin reintentos. Continuidad512 desde raíz roja original, T2I768×1376 reloj/llave/tejido y edit768×1376. HTTP200/PNG correcto/historial success sin errores en los tres. Total/job: 14,141/12,230s; 12,156/11,134s; 20,547/18,973s. Picos globales muestreados: 11687,11963,11588MiB de12288; margen mínimo325MiB. Sin OOM registrado, sin garantía para mayores cargas ni benchmark comparativo; baselines/caches distintos.

Revisión informal: continuidad conserva identidad/encuadre y añade luz dorada/vapor; T2I produce detalle fino pero incumple no-letras mediante inscripción inventada. Se conserva como resultado semántico parcial. No repetir T2I: la tercera edición prevista añadió retirada de inscripción al cambio del tejido a burdeos; ambos logrados visualmente con reloj/llave/detalles conservados. No confundir esa corrección con aceptación del T2I ni certificar invariancia exacta. [Informe](FLUX_KLEIN_4B_RESOLUTION_DETAILS.md), [registro completo](validation/flux-klein-4b-resolution-details-2026-10-07.json).

Assets/binario rehashados inicialmente; imágenes devueltas iguales a originales Comfy y dimensiones/historial revalidados al cierre. Cola vacía, bridge8091 cerrado/puerto libre, servicios originales vivos, hashes del source externo conservados y estable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61 intacto. Artifacts/harness ignorados bajo target/resolution-details-2026-10-07: preservar antes de archivar. Sin cambios de código, encoder BF16, grafos, dependencias, configuración, routing/QA/fallback; candidato planned. Solo documentación/evidencia: controles runtime/JSON/diff/enlaces/secretos, sin repetir tests históricos de código. Identificar SHA de cierre mediante historial de este archivo.

Pendiente vigente: dos referencias512 para roles/identidad/estilo y memoria, después multi-ref a resolución objetivo y caller MPT experimental/smoke de dos escenas. Continuidad y resolución ya tienen evidencia de estos casos; no repetir fases cerradas por ignorar los bloques históricos. No afirmar validación end-to-end ni promover a ready.

## Checkpoint 2026-10-08: caller MPT, multi-reference y QA experimental

Base limpia `1c7de1a707f0d51a631e027631f0da939567284b`, fetch sin divergencia. Encargo autónomo completó10 solicitudes Klein y2comparaciones, sin retry automático. Dos refs a512 y768×1376, orden invertido y seed43 funcionan técnicamente; fallos reales de marco por ambigüedad (corregido), geometría factual y llaves duplicadas/fusionadas (no corregido por cantidad explícita). Texto mitigado en un caso, tres agujas permanecen como fallo. Mínimo margen global muestreado387MiB en esta serie; histórico325MiB. Tres refs no ejecutadas por inestabilidad semántica y margen ajustado.

Integrado caller opt-in con aliases4B explícitos, roles/orden, calidad y conditioning separados, contrato temporal, un POST por intento, trazabilidad y fallback conservador solo por404 de modelo/workflow ausente. Fallo primario inyectado + secundario GPU real comprobados; no confundir con fallo natural. Bucle experimental fail-closed para QA no disponible/pass incierto, sin retries semánticos ni cambio automático de modelo.241tests+2subtests pasan,42casos nuevos; tests históricos intactos. [Contrato](FLUX_KLEIN_4B_MPT_INTEGRATION.md), [informe completo](FLUX_KLEIN_4B_AUTONOMOUS_REPORT.md).

Caller real y QA real ejercitados por separado, gates completos offline; no vídeo/planner→render vivo. QA reloj gross-pass/verdict-uncertain y temporal-uncertain no se aceptan. QA91,875–101,422s domina sobre generación12,796–33,203s en esos casos MPT. Comparación: Z-Image también tres agujas; Qwen conserva mejor la llave en un caso a mayor latencia observada. No ranking global ni promoción.

Candidato planned. Cola vacía,8091libre, servicios originales responden, bridge externo y stable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61 conservados. Artifacts y harnesses ignorados bajo target/autonomous-2026-10-08; JSON de validación los referencia con hashes. Siguiente tarea: evaluar QA de cantidad/detalle/estado en estos artifacts y reducir llamadas/captions duplicadas, antes de abrir tres referencias o routing automático. Obtener SHA de cierre del historial de este archivo.

Checkpoint de implementación: `599a680ec17ca37b5e8cddc78d6d475d88e1858f`. El checkpoint posterior conserva evidencias y handoffs; identificar su SHA con Git.


## Checkpoint 2026-10-08: QA sobre artifacts guardados

Base limpia87c7ba568b19ed48d041b625f269f5112f0ef4fd. Dataset16 casos, auditoría real del coste Florence/LLM y motor QA opt-in de cantidad/silueta/estado con caché, cortes tempranos y judge local acotado sin thinking. Commits1ec050a9b5dc2268dbf5a501b4b4fb663c659019 (dataset/auditoría) y d8de6a5195eecb6db6e242736fc4d5e89509d0ab (código/tests); identificar checkpoint de cierre mediante el historial del informe.

387tests+17subtests pasan,1 integración omitida, exit0. Matriz final:TP1/TN2/FP0/FN0,13uncertain/0unavailable; solo3/16decisiones (18,75%). Media4,5073s/mediana4,2692s, frente a69,169s del QA anterior instrumentado y91,875–101,422s históricos. No equivalencia de precisión: no se ha demostrado conteo fiable de agujas/llaves fusionadas ni identidad/progresión. Un judge sin thinking tomó7,8554s HTTP en un probe, pero luego hubo timeouts; no se demuestra incompatibilidad JSON grammar.

Zero nuevas generaciones/benchmarks GPU/descargas/dependencias/workflows/jobs/restarts. No flags persistidos, ni routing/promotion. Contratos vacíos no verifican Klein; requisitos factuales/continuidad quedan fail-closed sin identidad fuerte. Stable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61 intacto, backups untracked conservados; cola0/0,8091 no iniciado.

[Informe QA](VISUAL_QA_REPORT.md), [handoff QA](VISUAL_QA_HANDOFF.md), [dataset](validation/visual-qa-dataset-2026-10-08.json), [matriz final](validation/visual-qa-final-results-2026-10-08.json), [tests](validation/visual-qa-final-tests-2026-10-08.txt). Siguiente: evaluar visión fuerte sobre el mismo dataset y adjudicar labels independientemente. El servidor8080 declara vision=false; cualquier descarga o modelo/dependencia pesada requiere una decisión separada. No seguir generando para suplir esa falta de evidencia.


## Candidate judge preparation — 2026-10-08

User authorized download/evaluation of Qwen3.5-9B and Qwen3-VL-8B. Downloads/projectors/runtime SHA verified,51 offline tests pass. Comparative GPU evaluation remains pending clearance of shared8080 VRAM/RAM; no candidate verdicts or selection yet. [Current operational handoff](VISUAL_JUDGE_CANDIDATES_HANDOFF.md). No production/routing/dependency changes or new images.


## Visual judge comparison completed — 2026-10-08

Execution base8ebbb17480f07dd6235ff9b66a65d7dc2a3edbe7. User closed8080, then42 VLM requests on retained artifacts (0 generated images). Base V2:16 unique cases each;9B TP4/TN9/FP0/FN2, no unavailable, mean27.786s/median29.099s, peakglobal10448MiB;8B TP0/TN7/FP0/FN6,3unavailable, mean31.592s/median31.164s, peakglobal11299MiB. Unknown cold label excluded from binary confusion. Select Qwen3.5-9B Q4_K_M/F16 for next experimental phase only, not ready/admission/routing.

55 focused offline tests pass, exit0. No production/default/dependency/workflow changes. Own8092 closed,Comfy queue0/0, stable HEAD/tracked tree intact; user can reopen original8080 launcher. ROI/blind-count diagnostic and maxLength control timed out; exact cause unresolved, no sole grammar attribution. Next: isolate ROI prefill and verify blind counts/structural evidence before opt-in integration. [Full report](VISUAL_JUDGE_COMPARISON_REPORT.md), [handoff](VISUAL_JUDGE_CANDIDATES_HANDOFF.md). Preserve model weights/projectors/runtime/logs/crops under ignored target.


## Diagnóstico QA en reposo — 2026-10-08

Sobre9f42964: usuario cerró8080 y el juego. Se conservó un timeout de texto bajo carga del juego; una ejecución nueva en reposo completó6 controles independientes. Conteo ciego sobre imagen completa detecta3 agujas en negativo MPT; positivo completo/completo+crop cuenta2, crop aislado inventa3. Son solo2 imágenes y preguntas de conteo, sin validar el contrato completo ni la llave deformada.7 nuevas solicitudes de modelo,0 generaciones/descargas/cambios de producción. Jueces8092 cerrados;58 tests offline son del checkpoint de preparación, no un nuevo pytest. Ver [informe diagnóstico](VISUAL_JUDGE_PREFILL_DIAGNOSIS.md) y [handoff vigente](VISUAL_JUDGE_CANDIDATES_HANDOFF.md). Siguiente: conteo ciego en QA completo y geometría factual comparada con referencias; preservar OCR y fail-closed, sin routing automático.


## Contrato QA ciego y geometría factual — 2026-10-08

Base0624618.19 nuevas inferencias sobre imágenes existentes,0 generaciones/cambios productivos. Contrato completo16 casos:TP5/TN9/FP0/FN1,0timeouts,media9.125s,pico global7505MiB; tres agujas MPT detectadas, llave deformada aún aceptada. Control separado3 casos por componentes detecta llave pero rechaza2 positivos,uno por geometría y otro por texto con status/reason contradictorios. No cambiar labels ni rescatar verdict por reinterpretar reason. No ready/admisión/routing. Servidores propios cerrados y estable intacto. [Informe completo](VISUAL_JUDGE_FULL_QA_REPORT.md), [handoff vigente](VISUAL_JUDGE_CANDIDATES_HANDOFF.md). Siguiente: revisión independiente de geometría y evidencia estructurada por referencia/candidato antes de una integración opt-in de veto que preserve OCR/fail-closed.


## Observación geométrica independiente — 2026-10-08

Baseab4b032.4 inventarios sobre imágenes individuales, sin labels/roles/desired counts/verdict;4.727–6.556s. Comparador offline siempreuncertain/admission_allowed=false, aunque coincidan atributos. Agujero del negativo detectado como hint; conteos de componentes aún inconsistentes en un positivo.69 tests pasan,0 generaciones/descargas/dependencias/workflows/app/routing changes. Servidor propio cerrado y estable intacto. [Informe](VISUAL_GEOMETRY_OBSERVATIONS_REPORT.md), [revisión humana A/B/C](VISUAL_GEOMETRY_BLIND_REVIEW.md) solicitada y pendiente. Siguiente: registrar anotación humana separada y validar evidencias antes de cualquier integración factual. No convertir agreement en pass ni hints en veto automático.


## Revisión humana A/B/C recibida — 2026-10-08

Sobre3d60ade, el usuario confirma: A conserva forma con anillos ligeramente mayores; B cambia totalmente la forma; C conserva sin cambio visible. [Anotación separada](validation/visual-geometry-human-review-2026-10-08.json), labels/resultados antiguos intactos. Inventario A sin hints pierde matiz de tamaño; B tiene hints compatibles con alteración grave; C tiene falsas alarmas de conteo. La salida sigueuncertain/no admisión. No convertir A en igualdad exacta ni derivar un umbral productivo de3 pares.0 nuevas inferencias/generaciones/tests/cambios app. [Informe actualizado](VISUAL_GEOMETRY_OBSERVATIONS_REPORT.md). Siguiente: política experimental de avisos por severidad/observación insuficiente y controles adicionales antes de integrar, manteniendo OCR/fail-closed.


## Prioridades de avisos offline — 2026-10-08

Sobre61c1285 se implementó geometry-review-priorities-1 en script experimental: presencia distinta exige revisión estructural, conteos distintos revisión de medición, evidencia incompleta permanece explícita, anotaciones humanas separadas. Replay A/B/C sin nuevas inferencias; variación leve A procede del usuario, no del modelo. Nunca pass/identity ni rechazo automático; unavailable ante inventarios inválidos/transport incompleto.87 tests pasan,18 nuevos+69 previos;0GPU/generaciones/app/routing/dependencies/workflows. [Informe](GEOMETRY_REVIEW_PRIORITIES_REPORT.md). Siguiente: controles perceptuales con otra familia de objetos antes de integración opt-in de diagnóstico.


## Segunda familia: tazas — 2026-10-08

Baseb51e2b3. Observador generalizado con --plan;5 inferencias sobre tazas existentes,5.664–6.484s,92 tests aprobados. Inventarios coinciden en los4 atributos pese a color/vapor,0hints; prioridades siempreuncertain/no admisión/rechazo. No asumir identidad: faltan hueco del asa/contactos detallados y negativo estructural adjudicado. Labels de estado no se convierten en verdad geométrica; estado frío sigueincierto.0generaciones/deps/workflows/app/routing,servidor propio cerrado,estable intacto. [Informe](MUG_GEOMETRY_OBSERVATION_REPORT.md). Siguiente: presencia explícita del target y cobertura de partes con control de ausencia usando artifacts existentes.


## Presencia y cobertura de componentes — 2026-10-08

Base631afff. Nuevo perfil opcional preserva legacy. V1 rechaza targetpresent/partsnot_applicable y detiene5pendientes; V2 con ramasoneOf identifica taza presente y target ausente en reloj/llave,pero marca partes visiblesabsent. Descripción libre sí identifica boca/dos contactos; prompt/formato difieren,no causa única probada.4requests reales,0generaciones/retries/app/routing/deps/workflows.109tests finales pasan;coveragepolicy offline marca no_observed_component sin reescribirraw. Comparacionesuncertain/unavailable,nuncaadmisión. [Informe](TARGET_COMPONENT_OBSERVATIONS_REPORT.md). Siguiente: contraste same-prompt/same-budget con/sin schema antes de atribuir limitación visual o cambiar candidato.
