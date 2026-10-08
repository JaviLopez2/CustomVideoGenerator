# Auditoría e investigación de routing de imágenes

## Actualización — controles aislados, 2026-10-08

Base `3e2b873`: 20 nuevas requests retenidas, 0generaciones. Un componente por prompt/schema preserva definición, presupuesto, modelos y píxeles; ambos detectan hueco del asa/ausencia, pero contactos y bandas no se separan consistentemente. B continúa sin señal de conteo pese a revisión humana de cambio total. No se publica accuracy ni gold de regiones del asistente. [Evidencia y siguiente auditoría espacial independiente](ISOLATED_COMPONENTS_REPORT.md).

96 tests enfocados actuales pasan, exit0; código de app/harness/tests intacto. Replays/SVG preservan raw y píxeles; no adopción, default/config/gate/routing/deps/workflow/estable modificados. Los resultados multi-componente y suite520+17 anteriores se conservan históricos, sin atribución como nueva prueba. No ampliar presupuesto o buscar pass con nuevos prompts.

## Actualización — inspección espacial, 2026-10-08

Continuación desde `fe63c61`: boxes de sitios normalizadas con validación y hints IoU, diagramas SVG de revisión y replay offline. 5 requests nuevas sobre retenciones, 0 generaciones: Qwen3.5 tiene desplazamiento de regiones y truncación; Qwen3-VL completa controles pero omite hueco visible del asa/agrega contactos. No nuevo ranking universal ni métricas de accuracy/peak VRAM; inspección del asistente distinta de anotación gold. [Evidencia y límites](VISUAL_LOCATION_DIAGNOSTICS_REPORT.md).

520 tests +17 subtests pasan, 1 omitido, exit0. Defaults/caller gates/flags/routing/modelos/deps/workflows/estable intactos. Pendiente concreto: evaluación por componente con regiones revisadas independientemente, antes de adopción o vídeo completo. Se conservan resultados e investigaciones de fases históricas abajo.

## Actualización experimental — 2026-10-08

Base `7c1871c`: 11 nuevas inferencias VLM sobre imágenes retenidas, 0 generaciones. Contraste del mismo prompt/presupuesto variando solo response_format y posterior formato explícito: JSON mejora, pero contactos/bandas se agregan y aparece contradicción entre estado observado y descripción de ausencia. Los cuatro inventories de llave no priorizan B pese a la revisión humana de deformación total. No se habilita factual admission ni se presenta una tasa de precisión. [Informe con evidencia, fuente oficial y límites](COMPONENT_DECODING_DIAGNOSTICS_REPORT.md).

Se conectó únicamente replay offline de report SHA-pinned al caller privado experimental, por argumento explícito default None. Píxeles actuales/hash/raw provenance, sin modelo/red, etiquetas/verdicts ni autoridad QA/retry. 495 tests +17 subtests pasan, 1 integración omitida, exit 0. Stable intacto, servidores propios cerrados; modelos/deps/workflows/defaults/routing sin cambios. Siguiente tarea: coordenadas y revisión visual de ubicaciones sobre controles existentes. La fecha y alcance de auditoría original siguientes son históricos.

Fecha de consulta: 2026-10-07. Alcance: auditoría y documentación; ningún cambio de producción, modelo, dependencia o workflow, ninguna descarga de pesos, generación o benchmark.

## Recuperación y procedencia

El usuario informa de que el agente remoto creó estos documentos en el commit local `ab8e483`, pero no terminó su publicación. Su contenido y objeto Git no se recuperaron. Este documento se reconstruye desde el repositorio Windows disponible, el historial y el encargo actual; no es una copia de aquel commit ni certifica sus fases o conclusiones.

Base de código auditada: `7b2c303196fe16f9844a9ba3f081e8f296bc1dd9`. Checkpoint de preparación local publicado: `e759b39072bb32959ad06d86106c21f7da3b117a`, rama `factory/image-model-routing-modernization`. Se conservó el historial, sin reset ni force-push. Ver [handoff de investigación](IMAGE_MODEL_ROUTING_HANDOFF.md) y [handoff local](LOCAL_WINDOWS_ACCESS_HANDOFF.md).

Etiquetas de evidencia:

- **Local observado:** lectura de código, configuración seleccionada sin secretos, inventarios GET, tamaño de archivos o consulta de hardware. No equivale a una generación validada.
- **Publicado:** afirmación o parámetro de una fuente oficial enlazada, consultada en la fecha indicada. Sus cifras no son mediciones de esta RTX 3060.
- **Estimación:** inferencia técnica que necesita validación posterior; no hay cifras nuevas de latencia, calidad, pico de VRAM ni throughput de MPT.

## Estado realmente existente

La configuración local del worktree establece Standard=`z-image-turbo`, Precision=`qwen-image-2.1-precision`, fallback=`flux-klein-precision`, perfil=`balanced`. `config.toml` es configuración privada local: no se copia ni se publica.

En `app/services/material.py`:

- `_openai_image_model_for_route` resuelve Standard/Precision; si falta un modelo Precision utiliza el modelo por defecto y registra el fallback.
- `_openai_image_size`, `_openai_image_generation_steps` y `_precision_candidate_count` dan precedencia a los ajustes del perfil Qwen. Balanced local corresponde a `768x1376`, 20 pasos y un candidato. Los campos genéricos locales `864x1536` y dos candidatos no describen por sí solos el comportamiento efectivo de Balanced.
- El payload Qwen lleva `steps`, `seed` y referencias. El bridge externo inspeccionado aplica `steps` a `KSampler`; sus templates Qwen mantienen 25 pasos cuando no hay override. No se comprobó la identidad del binario bridge que está ejecutándose con ese source.
- El selector de referencias de escena limita el pack habitual a tres; el constructor de payload admite hasta diez. No confundir capacidad del modelo/payload con selección efectiva de escenas.
- La continuidad puede promover la escena a Precision (`continuity_edit_from_root`). La ruta finalmente ejecutada no se deduce solo de la ruta inicial del planner.
- El fallback de generación solo se intenta ante fallo primario con referencias y otras condiciones del código; transmite la primera referencia. No conserva automáticamente el pack completo ni cubre toda generación sin referencias.

El historial ya contiene los cambios siguientes; no se reimplementaron ni se atribuyeron nuevas pruebas a sus regresiones:

| Commit | Trabajo conservado |
| --- | --- |
| `5d96c35` | Routing de outputs temporales y predicados de estado |
| `82adca7` | Generación Precision sin referencia para outputs semánticos |
| `48eb383` | Regresiones de promoción semántica y Precision sin referencia |
| `721cd53` | Edición temporal de continuidad que preserva contenido en blanco |
| `f7f4c71` | Deduplicación de expresiones de continuidad |
| `0785ef1` | Regresiones de estados temporales en prompts Qwen |
| `7b2c303` | Regresión adicional de deduplicación |

Los tests relevantes existen en `test/services/test_evidence_pruning_root_qa.py` y `test/services/test_corrective_continuity.py`. Se inspeccionaron, no se ejecutaron en esta fase documental. Los handoffs anteriores registran validaciones históricas; no son resultados nuevos de Windows.

## Stack local e inventario

ComfyUI externo: `C:\Users\JAVIER\ComfyUI-Installs\ComfyUI\ComfyUI`, commit `73c9bad4d21e7addbe1d13bc92eee0f1431b017d`. El snapshot del repositorio declara ese mismo commit. Bridge externo: `D:\Comfyui2Openai\apps\api`; workflows en su carpeta `workflows`.

Consultas GET de solo lectura: 8080 `/health`=200; 8090 `/`=404; 8188 `/system_stats`=200. `/object_info` registra todos los tipos de nodo de los tres workflows inspeccionados. El registro de nodos no acredita validación completa del grafo ni ejecución del workflow.

| Alias del workflow externo | Pesos y parámetros observados | Inventario del servidor vivo |
| --- | --- | --- |
| `z-image-turbo` | `z_image_turbo_bf16.safetensors`, `qwen_3_4b.safetensors`, `ae.safetensors`; 8 pasos, CFG 1, `res_multistep` / `simple`, VAE tiled | Tres assets listados |
| `qwen-image-2.1-precision` | `qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_int8_convrot.safetensors`, `qwen_image_2.1_vae_bf16.safetensors`; template 25 pasos, CFG 1, `euler` / `simple`, cache auto, VAE tiled | Tres assets listados |
| `flux-klein-precision` | `flux-2-klein-9b-kv-fp8.safetensors`, `qwen_3_8b_fp8mixed.safetensors`, `flux2-vae.safetensors`; 4 pasos, CFG 1, `FluxKVCache`, VAE tiled | DiT listado; encoder y VAE no listados |

El último alias corresponde a **Klein 9B KV**, no a 4B. El encoder y VAE de ese workflow no se encontraron en las carpetas convencionales ni en las opciones de sus loaders vivos. Esto es un requisito faltante del grafo auditado, no un fallo de generación reproducido. No se corrigió ni se descargó nada; falta verificar además qué plantilla tiene cargada el bridge en memoria antes de afirmar que una petición actual fallaría.

El workflow Qwen del repositorio y el externo son iguales como JSON parseado; sus bytes difieren por serialización. No hay evidencia aquí de una divergencia funcional entre ambos. Los hashes de archivos externos se registran en [evidencia local](validation/image-model-routing-audit-2026-10-07.json).

Los nombres y tamaños de los pesos instalados no acreditan identidad criptográfica contra upstream. No se calcularon checksums de esos binarios ni se validó su procedencia completa; los hashes registrados corresponden a workflows JSON.

**Local observado:** RTX 3060, 12288 MiB totales, 9447 MiB ocupados en una única consulta `nvidia-smi`. Es ocupación global momentánea, sin atribución a un modelo ni a este agente. Tamaños de archivos: Z Turbo DiT 12309866400 bytes y encoder 8044982048; Qwen 2.1 DiT 7256783064 y encoder 9350798360; Klein 9B KV DiT 9818935984. Tamaño en disco no equivale a memoria residente o pico de inferencia. **Estimación:** coexistencia completa de esos componentes en 12 GB no debe darse por supuesta; offload, cachés, resolución, referencias, otros procesos y activaciones cambian el presupuesto.

## Candidatos y licencias: evaluación documental acotada

Esta selección se reconstruye ahora; no pretende recuperar una lista del commit remoto ausente ni ser un catálogo exhaustivo. Prioriza generación documental, identidad, edición y continuidad, licencia del modelo concreto y viabilidad en 12 GB. Ningún candidato queda adoptado por esta tabla.

| Modelo | Datos publicados y licencia | Soporte ComfyUI oficial | Juicio para 12 GB y estado |
| --- | --- | --- | --- |
| Z-Image-Turbo, baseline | 6B, destilado, 8 NFEs; Apache 2.0. El fabricante cita H800 para latencia subsegundo y dispositivos de 16 GB para memoria, no una medida en 3060. [Model card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) | [Workflow nativo](https://docs.comfy.org/tutorials/image/z-image/z-image-turbo) | Stack local con pesos/nodos presentes. Viabilidad operativa y calidad actuales sin medir; conservar como baseline, no promoverlo a editor por su nombre. |
| Qwen-Image-2.1, baseline Precision | 7B visual, generación y edición unificadas; admite hasta diez referencias según el fabricante. [Repositorio oficial](https://github.com/QwenLM/Qwen-Image-2.1). Licencia **Qwen Research**, uso de Materials limitado a investigación/evaluación no comercial; el texto exige licencia separada para uso comercial. [Licencia](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE) | [Workflow nativo y variantes INT8](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1) | Pesos/nodos locales presentes. Estimación: necesita administrar memoria por fases; no hay garantía de pico en 12 GB. No asumir Apache 2.0 ni autorización para un pipeline comercial. |
| FLUX.2 Klein 4B destilado | Generación y edición, cuatro pasos; Apache 2.0. [Licencia específica](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/main/LICENSE.md) | [Templates nativos T2I y edit](https://docs.comfy.org/tutorials/flux/flux-2-klein) | Prioridad documental para evaluar después por licencia, tamaño y edición. El nombre de peso FP8 del template no figura en el loader local; faltan inventario completo y prueba autorizada. No es el fallback instalado. |
| FLUX.2 Klein 4B Base | Variante no destilada, Apache 2.0; el repositorio oficial distingue Base de destilado. [Modelos oficiales](https://github.com/black-forest-labs/flux2) | [Template Base](https://docs.comfy.org/tutorials/flux/flux-2-klein) | Alternativa para estudiar calidad frente a coste; sin pesos esperados listados. No inferir que Base mejora continuidad en MPT sin evidencia. |
| Z-Image Base | 6B, Apache 2.0; recomienda 28–50 pasos y guidance 3–5. [Model card](https://huggingface.co/Tongyi-MAI/Z-Image) | [Template nativo](https://docs.comfy.org/tutorials/image/z-image/z-image) | Comparador opcional T2I; no sustituye un editor. Estimación: mayor trabajo de muestreo que Turbo; no convertir número de pasos en proporción de tiempo. Sin peso esperado listado. |
| Qwen-Image-Edit-2511 | Editor de 20B, Apache 2.0; el fabricante describe mejoras de consistencia. [Model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) | [Template nativo](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511) | Nodo `TextEncodeQwenImageEditPlus` registrado. El peso FP8 esperado no figura en el loader. Estimación: prioridad menor para 12 GB; 20B a 8 bits ya supone unos 20 GB solo de parámetros, sin encoder/activaciones. Cuantización adicional/offload requerirían revisión específica. |
| Klein 9B / 9B KV, fallback local | Licencia FLUX Non-Commercial para el modelo. [Familias oficiales](https://github.com/black-forest-labs/flux2). El texto distingue uso del modelo de uso de outputs: sección 2(d) admite usos comerciales de outputs sujeto a sus condiciones; no extiende ese permiso al despliegue comercial del modelo. [Licencia v2.1](https://github.com/black-forest-labs/flux2/blob/main/model_licenses/LICENSE-FLUX-NON-COMMERICAL) | Nodos del workflow local registrados; el template específico KV inspeccionado es el local | No prioritario como nuevo candidato de 12 GB; además faltan dos assets en el inventario vivo. No trasladar a 9B los permisos o cifras de 4B. |

**Publicado, con límites:** BFL muestra 8.4 GB para 4B destilado, 9.2 GB para 4B Base y 19.6 GB para 9B en su [tabla de producto](https://bfl.ai/models/flux-2-klein). Su [guía de ayuda](https://help.bfl.ai/articles/7592221790-how-do-i-generate-quickly-with-flux-2-klein) indica aproximadamente 13/24 GB para 4B/9B. Los contextos no están armonizados; ninguna cifra demuestra el pico de nuestro workflow, resolución, pack de referencias y RTX 3060. No se usan los tiempos de RTX 5090 o GB200 como predicción local.

La licencia del código de ComfyUI/bridge no sustituye la de pesos, encoder, VAE, adaptadores o referencias. Antes de una futura integración se debe fijar la variante y procedencia exactas de todos los componentes. No se descargaron ni inspeccionaron binarios nuevos para resolver esa revisión.

## Resultado y pendientes reales

Terminadas en esta fase: reconstrucción documental explícita, auditoría estática del routing/historial, comprobación de inventarios de los workflows actuales y revisión de fuentes oficiales/licencias/soporte para la selección acotada. Se preservaron las correcciones ya existentes.

Pendientes, **no completados**: recuperar `ab8e483` si el usuario lo aporta para reconciliar sus conclusiones; validar el workflow realmente cargado por el bridge; inventario/licencias de todos los componentes de un candidato elegido; pruebas locales de memoria, tiempo, identidad, continuidad y estado visible; integración y modificaciones de routing; comparación visual y promoción. Descargas, generación y benchmarks requieren autorización específica y quedan fuera de esta fase.

Siguiente tarea concreta propuesta: diseñar un plan de integración experimental de Klein 4B destilado, con IDs de modelo separados de 9B, manifiesto de assets/licencias, contratos de T2I/edición/referencias y tests offline de payload/fallback. Primero aclarar el fallback local incompleto y el uso previsto comercial/investigación. El plan no autoriza todavía instalar, cambiar routing ni ejecutar GPU.

## Actualización: contrato offline Klein 4B — 2026-10-07

Por el nuevo encargo del usuario se implementaron aliases experimentales T2I/Edit, manifiesto `planned` y tests offline, fuera de producción. Ver [plan y resultados](FLUX_KLEIN_4B_EXPERIMENT.md). No se activaron aliases en el bridge, no se exportaron grafos API y no se descargaron pesos. Los gates de archivos/licencias/hashes siguen cerrados. Una regresión adicional existente falla por capitalización; no se modificó ni se ocultó. El contrato offline no valida una generación real ni un candidato listo para promoción.

## Actualización: grafos API aislados — 2026-10-07

Continuación sobre `d4d32c4`: topología nativa reconstruida de los templates oficiales T2I/Edit Distilled, con selección 4B FP8, hashes versionados y aviso MIT. El adaptador offline materializa 0 o 1–3 referencias, encadena ambos conditionings y aplica seed/tamaño/4 pasos/CFG 1. No incorpora FluxKVCache. Se distingue reconstrucción de una exportación UI; la salida usa dimensiones del encargo en lugar de derivarlas de una referencia. Ver [contratos, diferencias respecto al bridge y límites](FLUX_KLEIN_4B_EXPERIMENT.md).

Publicado: topologías y parámetros de los templates oficiales, consultados de nuevo. Observado local: nodos, campos requeridos y tipos de enlaces compatibles mediante GET object_info, DiT/VAE ausentes en loaders, encoder listado sin hash verificado. Pruebas offline: 126 passed; suite adicional histórica 14 passed y 1 failed por capitalización. No hay mediciones GPU nuevas ni evidencia de calidad/memoria/latencia. Los grafos no están instalados ni los aliases registrados en el servicio. El candidato sigue `planned`, con hashes de pesos y revisiones de ejecución pendientes. La investigación documental no se reabre ni se presenta como certificación empírica de 12 GB.

## Actualización: gate de continuidad resuelto — 2026-10-07

Sobre `de11868`, se corrigió el prefijo de identidad del planner exclusivamente en el worktree experimental: `same`/`the same` pasan a `The same` sin cambiar el resto del nombre ni duplicar el prefijo. Los tests históricos permanecen intactos. Validación ampliada offline: **151 passed**, incluidas las 15 pruebas de la suite que antes fallaba y diez casos nuevos de identidad/estado. Ver [handoff y logs](IMAGE_MODEL_ROUTING_HANDOFF.md). Esto cierra el fallo observado en esas suites, sin probar toda la aplicación ni alterar el estado `planned`, assets o integración del candidato. No hay nuevas mediciones GPU ni cambios en las conclusiones de viabilidad/licencias.

## Actualización: identidad del encoder y preflight — 2026-10-07

Observado local: encoder `qwen_3_4b.safetensors`, 8.044.982.048 bytes, SHA-256 igual al publicado por Comfy-Org/z_image_turbo en revisión fijada. Cabecera con 398 tensores BF16, sin carga de tensores. El manifiesto ahora distingue hash local verificado del encoder de hashes esperados upstream para DiT/VAE aún ausentes. Publicado: VAE Comfy coincide en LFS con `vae/diffusion_pytorch_model.safetensors` BFL, no con `ae.safetensors`; la declaración Apache 2.0 del autoencoder se trata por componente, sin heredar la licencia `other` de toda la tarjeta dev. Ver [fuentes, evidencia y plan](FLUX_KLEIN_4B_INSTALL_PLAN.md).

Pendiente descargar 4.406.838.076 bytes con autorización específica. Espacio libre observado suficiente para esos archivos, sin inferir VRAM disponible o viabilidad GPU del conjunto. Contratos afectados: 39 passed en esta fase. No se reabre la selección de candidatos ni se ejecutan generaciones; estado `planned`, integración y mediciones locales pendientes.

## Actualización: assets instalados — 2026-10-07

Con autorización del usuario, sobre `99d6abd` se descargaron/verificaron DiT Klein 4B FP8 y VAE Flux2 (4.406.838.076 bytes). SHA-256 y tamaños locales coinciden con las revisiones oficiales fijadas. Encoder BF16 rehashado y conservado; no hay evidencia empírica para recomendar reemplazarlo. Ver [instalación y límites](FLUX_KLEIN_4B_INSTALL_PLAN.md). Contratos afectados: 39 passed.

Ninguna inferencia ni benchmark: los tipos de tensores y tamaños en disco no certifican memoria residente. GET posterior de Comfy en 8188 rechazado; inventario vivo no validado. Candidato sigue `planned` pese a los tres assets verificados. Integración de bridge, revisión efectiva de procesos, memoria, continuidad/calidad y promoción permanecen pendientes.

Revalidación tras `b3e1191`: ComfyUI responde por GET y lista los tres assets, bridge raíz responde 404 y MPT health 200. El rechazo anterior se conserva como evento histórico; inventario vivo ahora verificado, sin carga/inferencia ni inicio de servicios por el agente. No cambia la conclusión sobre memoria, calidad o promoción.

## Actualización: integración Rust aislada — 2026-10-07

Sobre `f38c63e`, preparado y compilado un bridge experimental separado, con aliases 4B, binding de parámetros y expansión de referencias/roles. Código externo y proceso 8090 intactos. Preview HTTP 8091 comprobado con dispatch bloqueado 403 y proceso terminado; mode GPU implementado para encargo posterior, no ejecutado. [Contrato y límites](../local_image_stack/experiments/bridge/README.md).

Validación: 173 tests Python + 1 Rust pasan, sin nuevas medidas GPU. La identidad del código/binary se registra en evidencia; no acredita revisión del proceso 8090 ni funcionamiento del modelo. Candidato `planned`; pendientes activación GPU mínima, memoria/calidad/latencia y caller MPT experimental con roles. Esta fase no cambia las conclusiones documentales de licencias/viabilidad.

## Actualización: primera medida GPU local autorizada — 2026-10-07

Sobre `066fcdd`, una única solicitud T2I 512×512, 4 pasos, seed 42, sin refs y con encoder BF16: HTTP 200 e imagen válida, historial Comfy success. 10,109 s de solicitud, 8,672 s de ejecución del job. Baseline global GPU 4424 MiB; pico global muestreado 11433 MiB de 12288, margen observado 855 MiB. [Datos, artifact y límites](FLUX_KLEIN_4B_GPU_SMOKE.md).

Esto sustituye la ausencia de mediciones para ese caso concreto; no valida cifras publicadas en otros equipos ni demuestra memoria de edición/resolución objetivo. Una sola imagen visualmente acorde al prompt, sin A/B/repetición ni control de caches. Candidato sigue `planned`; single-ref, continuidad, multi-ref, resolución objetivo, caller MPT y promoción pendientes. No hubo otra generación ni cambios de producción.

## Actualización: single-ref local — 2026-10-07

Una edición autorizada sobre `a3d82a2`: taza roja→azul profundo, output512×512, una referencia identity escalada a1MP, 4 pasos/seed42. HTTP200 e historial success; 14,219s solicitud y13,926s job. Pico global muestreado11756/12288MiB (baseline4264), margen532MiB. Cambio logrado y conservación visual de forma/escena en revisión informal. [Datos y límites](FLUX_KLEIN_4B_SINGLE_REF_SMOKE.md).

Se cierra solo ese caso de edición, sin validar exactitud geométrica, repetibilidad, temporal, multi-ref, resolución objetivo o pipeline MPT. Memoria global/caches no controladas y margen pequeño; no extrapolar a mayores cargas. Candidato `planned`; ninguna otra generación ante la pregunta del usuario sobre complejidad.

## Actualización: continuidad, resolución y detalle medidos localmente

Sobre `6ba2402`, tres pruebas funcionales autorizadas con seed42/4 pasos/guidance1 y encoder BF16 sin cambios. Continuidad512: atardecer/vapor con identidad y encuadre visualmente conservados,14,141s. T2I768×1376: reloj/llave completos y detalle de metal/tejido,12,156s; resultado semántico parcial por inscripción inventada pese al prompt sin letras. Edit768×1376: tejido burdeos y retirada de esa inscripción conservando visualmente objetos/detalles,20,547s. Tres historiales success sin errores; ninguna repetición. La edición correctora no elimina el fallo original del T2I. [Informe y límites](FLUX_KLEIN_4B_RESOLUTION_DETAILS.md).

Datos medidos: picos globales muestreados11687/11963/11588MiB de12288, mínimo margen325MiB; baselines/caches no controladas. Sin OOM en estos tres casos, sin estimar memoria por modelo ni garantizar mayores resoluciones/multi-ref. Juicios de calidad son visuales informales; no benchmark objetivo/repetido ni A/B. No se reabre investigación documental/licencias ni se presentan estas mediciones como cifras publicadas. Candidato planned; multi-ref y caller/pipeline MPT siguen pendientes. Código/grafos/encoder/producción intactos.

## Checkpoint 2026-10-08: caller MPT, multi-reference y QA experimental

Base limpia `1c7de1a707f0d51a631e027631f0da939567284b`, fetch sin divergencia. Encargo autónomo completó10 solicitudes Klein y2comparaciones, sin retry automático. Dos refs a512 y768×1376, orden invertido y seed43 funcionan técnicamente; fallos reales de marco por ambigüedad (corregido), geometría factual y llaves duplicadas/fusionadas (no corregido por cantidad explícita). Texto mitigado en un caso, tres agujas permanecen como fallo. Mínimo margen global muestreado387MiB en esta serie; histórico325MiB. Tres refs no ejecutadas por inestabilidad semántica y margen ajustado.

Integrado caller opt-in con aliases4B explícitos, roles/orden, calidad y conditioning separados, contrato temporal, un POST por intento, trazabilidad y fallback conservador solo por404 de modelo/workflow ausente. Fallo primario inyectado + secundario GPU real comprobados; no confundir con fallo natural. Bucle experimental fail-closed para QA no disponible/pass incierto, sin retries semánticos ni cambio automático de modelo.241tests+2subtests pasan,42casos nuevos; tests históricos intactos. [Contrato](FLUX_KLEIN_4B_MPT_INTEGRATION.md), [informe completo](FLUX_KLEIN_4B_AUTONOMOUS_REPORT.md).

Caller real y QA real ejercitados por separado, gates completos offline; no vídeo/planner→render vivo. QA reloj gross-pass/verdict-uncertain y temporal-uncertain no se aceptan. QA91,875–101,422s domina sobre generación12,796–33,203s en esos casos MPT. Comparación: Z-Image también tres agujas; Qwen conserva mejor la llave en un caso a mayor latencia observada. No ranking global ni promoción.

Candidato planned. Cola vacía,8091libre, servicios originales responden, bridge externo y stable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61 conservados. Artifacts y harnesses ignorados bajo target/autonomous-2026-10-08; JSON de validación los referencia con hashes. Siguiente tarea: evaluar QA de cantidad/detalle/estado en estos artifacts y reducir llamadas/captions duplicadas, antes de abrir tres referencias o routing automático. Obtener SHA de cierre del historial de este archivo.


## Checkpoint 2026-10-08: QA sobre artifacts guardados

Base limpia87c7ba568b19ed48d041b625f269f5112f0ef4fd. Dataset16 casos, auditoría real del coste Florence/LLM y motor QA opt-in de cantidad/silueta/estado con caché, cortes tempranos y judge local acotado sin thinking. Commits1ec050a9b5dc2268dbf5a501b4b4fb663c659019 (dataset/auditoría) y d8de6a5195eecb6db6e242736fc4d5e89509d0ab (código/tests); identificar checkpoint de cierre mediante el historial del informe.

387tests+17subtests pasan,1 integración omitida, exit0. Matriz final:TP1/TN2/FP0/FN0,13uncertain/0unavailable; solo3/16decisiones (18,75%). Media4,5073s/mediana4,2692s, frente a69,169s del QA anterior instrumentado y91,875–101,422s históricos. No equivalencia de precisión: no se ha demostrado conteo fiable de agujas/llaves fusionadas ni identidad/progresión. Un judge sin thinking tomó7,8554s HTTP en un probe, pero luego hubo timeouts; no se demuestra incompatibilidad JSON grammar.

Zero nuevas generaciones/benchmarks GPU/descargas/dependencias/workflows/jobs/restarts. No flags persistidos, ni routing/promotion. Contratos vacíos no verifican Klein; requisitos factuales/continuidad quedan fail-closed sin identidad fuerte. Stable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61 intacto, backups untracked conservados; cola0/0,8091 no iniciado.

[Informe QA](VISUAL_QA_REPORT.md), [handoff QA](VISUAL_QA_HANDOFF.md), [dataset](validation/visual-qa-dataset-2026-10-08.json), [matriz final](validation/visual-qa-final-results-2026-10-08.json), [tests](validation/visual-qa-final-tests-2026-10-08.txt). Siguiente: evaluar visión fuerte sobre el mismo dataset y adjudicar labels independientemente. El servidor8080 declara vision=false; cualquier descarga o modelo/dependencia pesada requiere una decisión separada. No seguir generando para suplir esa falta de evidencia.


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
