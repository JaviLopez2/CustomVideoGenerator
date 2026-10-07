# Handoff de auditoría de modelos — 2026-10-07

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
