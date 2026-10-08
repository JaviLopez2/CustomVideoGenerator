# Preparación de acceso local — 2026-10-07

Alcance: preparar operación autónoma en este Windows. Modernización detenida; sin tests, benchmarks, generación, cambios de dependencias ni cambios de servicios.

## Estado comprobado antes de añadir documentación

- Carpeta: `D:\Apps\MPT-worktrees\image-model-routing-modernization`.
- Rama: `factory/image-model-routing-modernization`.
- HEAD de partida: `7b2c303196fe16f9844a9ba3f081e8f296bc1dd9`.
- Status y diff staged/unstaged vacíos. `git worktree list` confirma diez worktrees, incluida la copia estable.
- Se añadió únicamente `AGENTS.md` y este handoff, conservando los documentos existentes. El checkpoint documental posterior se identifica en el historial Git; el HEAD anterior no es su SHA.

## Accesos comprobados

- Lectura de Factory, `data\runs` (20 entradas), un `worker.log`, ComfyUI y bridge mediante ejecución fuera del sandbox aprobada por el mecanismo de revisión de la sesión.
- Python MPT configurado por Factory: `D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe`, versión 3.11.15; pytest disponible. Probe con `-I -B`, sin importar MPT ni ejecutar tests.
- La configuración experimental Factory apunta a este worktree y a esta rama. No se modificó.
- GET local con timeout de 3 segundos: 8080 `/health` = 200; 8090 `/` = 404; 8188 `/system_stats` = 200. No certifican calidad ni generación.
- No había `AGENTS.md` en el worktree ni en los directorios superiores comprobados. Se leyó el existente de ComfyUI y los handoffs de MPT/Factory.

## Permisos y limitaciones

- La sesión declara el worktree experimental como escribible y usa `approvals_reviewer=auto_review`. Las escalaciones de lectura se ejecutaron correctamente; esto no concede permisos permanentes a futuras operaciones.
- El ejecutor restringido falla antes de iniciar PowerShell: `helper_unknown_error: setup refresh had errors`.
- La configuración local de Codex ya indica `[windows] sandbox = "elevated"`; no se cambió la configuración global ni las ACL.
- El log documentado `C:\Users\JAVIER\.codex\.sandbox\sandbox.log` contiene un error del 2026-04-16: `helper_firewall_rule_create_or_add_failed`, `SetRemotePorts`, HRESULT `0x80070057`. Es un antecedente, no prueba de la causa del fallo actual.
- No hay una herramienta de esta sesión para modificar el selector de permisos o rehacer la instalación del sandbox. No se requiere acceso completo para los accesos ya comprobados mediante escalación.
- Si se necesita reparar el sandbox ordinario: reiniciar Codex y reintentar la configuración de Agent sandbox cuando la interfaz la ofrezca; el usuario debe aceptar el diálogo UAC si aparece. Referencia: https://learn.chatgpt.com/docs/windows/windows-sandbox.
- Mantener el selector de permisos en `Approve for me` / `Aprobar por mí` para revisión automática de escalaciones elegibles; ya está activo en esta sesión. Referencia: https://learn.chatgpt.com/docs/sandboxing.
- Metadatos Git compartidos: `D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\MoneyPrinterTurbo\.git`, fuera de la raíz escribible. Solicitar escalación específica para checkpoints experimentales si procede; mantener protegidos el árbol estable y sus ramas.

## Continuación

Esperar una nueva tarea. Ejecutar comandos, editar y validar dentro de su alcance, conservar cambios existentes, guardar logs y checkpoints con handoff. No retomar la modernización por iniciativa propia. Las reglas y comandos de tests están en `AGENTS.md`.

## Primera tarea autónoma: publicación e investigación — 2026-10-07

La nueva tarea autoriza fetch, publicación de commits válidos e investigación documental, manteniendo prohibidos cambios de modelos/routing/workflows/dependencias, descargas de pesos, generaciones y benchmarks.

- HEAD inicial: `e759b39072bb32959ad06d86106c21f7da3b117a`; worktree limpio. Se revisaron instrucciones y handoffs locales antes de actuar.
- `git fetch origin` terminó correctamente. Remoto experimental: `7b2c303196fe16f9844a9ba3f081e8f296bc1dd9`. `git rev-list --left-right --count HEAD...origin/factory/image-model-routing-modernization` = `1 0`: solo el checkpoint local de preparación, sin divergencia.
- Revisión de `AGENTS.md` y este handoff: cero coincidencias con patrones de claves OpenAI/GitHub/AWS, claves privadas, asignaciones de secretos literales y URLs con credenciales. Es una comprobación por patrones, no una garantía exhaustiva. No se imprimieron secretos.
- `git push origin HEAD:refs/heads/factory/image-model-routing-modernization` falló: GitHub rechazó las credenciales. No se realizó force-push ni se alteró el historial local.
- GitHub CLI no está disponible; no hay `GH_TOKEN` ni `GITHUB_TOKEN` en el entorno del proceso. Git Credential Manager 2.6.1 está disponible; falta completar autenticación válida antes de publicar.
- `docs/IMAGE_MODEL_ROUTING_RND.md` y `docs/IMAGE_MODEL_ROUTING_HANDOFF.md` no existen en este checkout ni aparecen en `git log --all --` para esos paths tras fetch. Tampoco se encontraron por nombre en los worktrees MPT o Factory, incluidos archivos ignorados (excluidos caches, modelos, storage y metadatos Git), ni en la búsqueda inicial de la copia estable.
- El contexto recuperable de `Implementar MPT Agent Factory` referencia los dos documentos, pero no recuperó su contenido. Se pidió al usuario identificar su rama/carpeta/chat de origen y resolver el login. No se enviaron mensajes a otros chats.
- Contraste preliminar de código: `app/services/material.py::_openai_image_model_for_route` sigue seleccionando el modelo configurado Standard/Precision, con fallback al modelo por defecto cuando falta Precision. El historial reciente contiene fixes y regresiones de fallback semántico, edición temporal y deduplicación de prompts; no acredita por sí solo una auditoría de candidatos terminada. No se repitieron esos fixes.
- No se inició investigación de candidatos sin conocer las fases ya realizadas. No se crearon documentos sustitutos ni se atribuyeron resultados o mediciones inexistentes. No se ejecutaron tests de aplicación, generaciones, benchmarks ni descargas.

Bloqueos para cerrar la fase: recuperar el handoff real y autenticar Git para escritura en origin. Siguiente acción concreta: completar esos dos requisitos, volver a hacer fetch/comparar, publicar los checkpoints locales sin force-push y continuar solo los pendientes identificados en los documentos recuperados. El checkpoint de este diagnóstico se identifica en el historial Git; la fase solicitada permanece incompleta.

### Resolución durante la misma tarea

El usuario aclaró que los documentos solo existían en el commit local remoto `ab8e483`, sin publicar, y autorizó reconstruirlos desde este repositorio. También autorizó login con Git Credential Manager mediante navegador; terminó correctamente. Tras otro fetch sin divergencia, se publicó `e759b39072bb32959ad06d86106c21f7da3b117a` y `git ls-remote` confirmó ese SHA. Los bloqueos anteriores describen el estado inicial, no el cierre.

Se crearon `docs/IMAGE_MODEL_ROUTING_RND.md` y `docs/IMAGE_MODEL_ROUTING_HANDOFF.md`, con auditoría estática, revisión oficial de candidatos/licencias/ComfyUI y separación de observaciones, datos publicados y estimaciones. No se recuperó ni se fingió el contenido de `ab8e483`. Ver el nuevo handoff y su registro de comprobaciones. Solo cambian documentos y evidencia JSON; la modernización de producción sigue pendiente de un nuevo encargo.

### Continuación experimental offline — 2026-10-07

Sobre `d4d32c4` se prepararon grafos API Klein 4B y adaptador offline aislados, con permisos específicos de comandos en Windows. Fetch funciona sin divergencia. GET de Comfy `/object_info` funciona; validación de campos y tipos de enlaces registrada en `validation/flux-klein-4b-api-schema-2026-10-07.json`. Tests ejecutados con el Python portable MPT: 126 passed; suite histórica adicional 14 passed y 1 failed, sin alterar sus archivos. No se instalaron assets, no se activó integración, no se ejecutó generación ni se modificó la copia estable. Ver el checkpoint vigente de `IMAGE_MODEL_ROUTING_HANDOFF.md` para alcance y pendientes.

### Cierre del gate histórico — 2026-10-07

Continuación autorizada sobre `de11868`: corrección mínima del prefijo del planner en el worktree experimental, conservando todos los tests históricos. Python portable ejecutó 25 tests enfocados y 151 en la validación ampliada, todos aprobados. Logs `validation/continuity-prefix-*-2026-10-07.txt`; alcance y siguiente tarea en `IMAGE_MODEL_ROUTING_HANDOFF.md`. No se modificó ni desplegó la copia estable, ni se ejecutaron modelos/servicios/GPU. Los permisos siguen siendo los efectivos de la sesión; el uso de escalaciones específicas no concede permisos permanentes.

### Preflight de assets — 2026-10-07

Sobre `57a5747`: lectura completa del encoder Comfy funciona; hash y tamaño coinciden con la distribución oficial fijada. GET de metadatos públicos HF funciona sin autenticación; no se usaron ni guardaron tokens. Espacio y ausencia de destinos DiT/VAE comprobados en lectura. Contratos afectados: 39 passed. Plan y evidencia en `FLUX_KLEIN_4B_INSTALL_PLAN.md` y `validation/flux-klein-4b-asset-preflight-2026-10-07.json`. No se probó escritura en los destinos externos, ni se descargaron pesos; su instalación futura necesita autorización de alcance y escalaciones específicas, no cambios de permisos permanentes.

### Instalación autorizada — 2026-10-07

Sobre `99d6abd`, descarga/escritura específica en las dos carpetas de modelos Comfy funciona mediante escalación aprobada. DiT/VAE instalados tras validación de tamaño/SHA/cabecera; encoder sin cambios. No se guardaron credenciales ni URLs firmadas. GET posterior de Comfy en 8188 rechaza conexión; no se inició el servicio. 39 tests afectados pasan; evidencia `validation/flux-klein-4b-install-2026-10-07.json`. Los accesos de descarga no conceden permisos permanentes ni autorización de reinicio/GPU. Copia estable, Factory y servicios sin modificaciones.

Recheck tras publicación de `b3e1191` y oferta del usuario de abrir servidores: ComfyUI GET 200, tres assets listados; bridge raíz 404 y MPT health 200. La indisponibilidad anterior ya no es el estado vigente. Sin inicio/reinicio ni generación desde el agente; registro JSON actualizado conservando ambos eventos.

### Bridge experimental — 2026-10-07

Sobre `f38c63e`, Cargo/Rust 1.98.1 y cache local permiten build/test offline locked de `local_image_stack/experiments/bridge`. Source externo solo leído, sin cambios; hashes registrados. Preview HTTP efímero en loopback 8091 funciona, aliases listados y dispatch bloqueado 403; test cierra únicamente su proceso y libera el puerto. 173 tests Python + 1 Rust pasan. Sin POST Comfy/GPU ni cambios globales, de MPT estable o servicio 8090. Binario ignorado por Git; instrucciones reproducibles en README experimental, resultados/procedencia en validation.

### Una generación GPU autorizada — 2026-10-07

Sobre `066fcdd`, instancia experimental 8091 `--serve-gpu` creada para una sola solicitud T2I 512×512/4 pasos/seed42. GPU, endpoint y devolución PNG funcionan: HTTP200 e historial success, 10,109 s solicitud, 8,672 s job. Sensores nvidia-smi accesibles; pico global muestreado11433MiB de12288, baseline4424. JSON/artifacts/limitaciones en `FLUX_KLEIN_4B_GPU_SMOKE.md`. Instancia experimental cerrada, puerto libre, servicios originales responden. No reinicios ni modificaciones de estable/configuración/dependencias; no permisos permanentes nuevos ni autorización para más generaciones.

### Una edición single-ref autorizada — 2026-10-07

Sobre `a3d82a2`, input propio copiado a Comfy sin sobrescritura y una solicitud edit512×512/seed42/4 pasos: HTTP200, historial success, cambio rojo→azul visualmente logrado. Total14,219s/job13,926s, pico global muestreado11756/12288MiB. Instancia8091 cerrada, cola vacía, servicios originales vivos y estable intacto. Paths/evidencia en `FLUX_KLEIN_4B_SINGLE_REF_SMOKE.md`; sin cambios globales ni permiso para más generaciones por este paso.

### Serie autorizada de continuidad/resolución/detalles — 2026-10-07

Sobre `6ba2402`, tres solicitudes al bridge experimental8091: continuidad512, T2I768×1376 y edit768×1376; HTTP200 e historial success en las tres. Lectura de outputs/historial/sensores y staging sin sobrescritura de input propio funcionan. T2I parcial por inscripción inventada, retirada en edición posterior sin ocultar el fallo. [Informe](FLUX_KLEIN_4B_RESOLUTION_DETAILS.md). Pico global muestreado11963/12288MiB; no garantiza cargas mayores. Bridge propio cerrado y puerto libre, cola vacía, servicios originales vivos, stable HEAD y hashes source externo conservados. Solo documentación/evidencia añadidas; sin cambios globales, dependencias o permisos permanentes. Artifacts ignorados preservables en target/resolution-details-2026-10-07.

### Cierre autónomo — 2026-10-08

Comandos, pytest, lectura/escritura de inputs propios, generación secuencial, sensores, caller MPT aislado y QA local funcionan con escalaciones específicas. No permisos permanentes nuevos.10solicitudes Klein+2comparaciones;241tests+2subtests aprobados. Cola vacía/8091libre, servicios originales responden y stable/source externo conservados. Fallo puntual de revisión automática por límite de uso resuelto tras nuevo encargo de continuar; no se eludió la revisión ni duplicó el comando. Contrato y evidencias en [informe](FLUX_KLEIN_4B_AUTONOMOUS_REPORT.md). El principal bloqueo actual es calidad/admisión QA, no acceso.


## Checkpoint 2026-10-08: QA sobre artifacts guardados

Base limpia87c7ba568b19ed48d041b625f269f5112f0ef4fd. Dataset16 casos, auditoría real del coste Florence/LLM y motor QA opt-in de cantidad/silueta/estado con caché, cortes tempranos y judge local acotado sin thinking. Commits1ec050a9b5dc2268dbf5a501b4b4fb663c659019 (dataset/auditoría) y d8de6a5195eecb6db6e242736fc4d5e89509d0ab (código/tests); identificar checkpoint de cierre mediante el historial del informe.

387tests+17subtests pasan,1 integración omitida, exit0. Matriz final:TP1/TN2/FP0/FN0,13uncertain/0unavailable; solo3/16decisiones (18,75%). Media4,5073s/mediana4,2692s, frente a69,169s del QA anterior instrumentado y91,875–101,422s históricos. No equivalencia de precisión: no se ha demostrado conteo fiable de agujas/llaves fusionadas ni identidad/progresión. Un judge sin thinking tomó7,8554s HTTP en un probe, pero luego hubo timeouts; no se demuestra incompatibilidad JSON grammar.

Zero nuevas generaciones/benchmarks GPU/descargas/dependencias/workflows/jobs/restarts. No flags persistidos, ni routing/promotion. Contratos vacíos no verifican Klein; requisitos factuales/continuidad quedan fail-closed sin identidad fuerte. Stable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61 intacto, backups untracked conservados; cola0/0,8091 no iniciado.

[Informe QA](VISUAL_QA_REPORT.md), [handoff QA](VISUAL_QA_HANDOFF.md), [dataset](validation/visual-qa-dataset-2026-10-08.json), [matriz final](validation/visual-qa-final-results-2026-10-08.json), [tests](validation/visual-qa-final-tests-2026-10-08.txt). Siguiente: evaluar visión fuerte sobre el mismo dataset y adjudicar labels independientemente. El servidor8080 declara vision=false; cualquier descarga o modelo/dependencia pesada requiere una decisión separada. No seguir generando para suplir esa falta de evidencia.
