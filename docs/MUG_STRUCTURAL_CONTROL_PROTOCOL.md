# Control estructural de taza — protocolo previo, 2026-10-09

Estado: **preparado, pendiente de crear y revisar el negativo**. Base `d765e58a76650b6b8410f141eeaecf61deda287f`, rama `factory/image-model-routing-modernization`. Esta fase prepara archivos y comprueba contratos offline; no produce imágenes ni nuevas respuestas de los jueces. [Manifiesto](validation/mug-structural-control-protocol-2026-10-09.json), [petición de edición](validation/mug-structural-control-edit-request-2026-10-09.json).

## Pregunta y controles

¿Los candidatos ya instalados distinguen dos uniones visibles del asa de una sola, localizan cada unión por separado y conservan esa observación al cambiar únicamente el color? Se observan imágenes individuales; no se pide aprobar identidad física ni detectar un defecto nombrado en el prompt del juez.

| Caso offline | Imagen | Revisión necesaria antes de inferencia |
|---|---|---|
| Positivo rojo | Original retenido, 512×512; SHA comienza `16c94d6f` | Confirmar dos uniones directamente visibles. Los puntos históricos son aproximados, no gold. |
| Control de color azul | Edición retenida, 512×512; SHA comienza `a245930e` | Confirmar dos uniones; no atribuir invariancia exacta al nombre de la edición. |
| Negativo estructural | Una edición de la roja, mismo tamaño y encuadre solicitado; aún inexistente | Unión inferior visiblemente interrumpida, unión superior intacta y visible. |

Las imágenes y revisiones anteriores, incluidos A/B/C y el contorno B discutido, permanecen intactas. El control de ausencia de taza de la fase previa no sustituye este negativo estructural. Los positivos y sus resultados son conocidos: la nueva cohorte no es una evaluación ciega ni una estimación de accuracy poblacional.

## Creación y revisión del negativo

Una única petición a `http://127.0.0.1:8091/v1/images/generations`, alias aislado `flux-klein-4b-edit-exp`, referencia roja con rol `identity_reference`, seed42, 512×512, cuatro pasos, guidance1 y n1. Usar binario y workflows existentes del worktree; ninguna modificación o descarga. El prompt exacto queda fijado en el manifiesto antes de la edición. `--dry-run` materializa el grafo sin iniciar servicios ni enviarlo a ComfyUI.

Al ejecutar: comprobar instrucciones aplicables de ComfyUI, hashes y assets vivos, cola vacía, puertos 8091/8092 libres y recursos sin juego ni 8080 cargado. Solo ComfyUI compartido en8188 es necesario; 8090 no interviene. Iniciar y cerrar únicamente el bridge experimental propio, con ventana oculta. Crear una referencia de nombre único en el input de ComfyUI con escalación de escritura específica: si el nombre ya existe, comparar SHA y reutilizar solo si coincide; nunca sobrescribir otro archivo. No alterar configuración, flags, servicios compartidos o árboles protegidos.

Preservar petición, respuesta, prompt_id, historial y PNG con SHA. Presupuesto máximo: **una generación, cero reintentos/fallbacks**, 180s de espera HTTP. Un timeout deja ejecución potencialmente en curso: inspeccionar cola/historial por prompt_id antes de concluir; no reenviar ni interrumpir trabajos ajenos. El timeout no prueba cancelación.

Revisar primero el asistente y después el usuario un tablero con original y negativo completos, más detalle visible del asa. La respuesta humana debe confirmar: (1) separación inferior real y evidente, no sombra/reflejo; (2) unión superior intacta; (3) taza completa sin cambios importantes de forma, perspectiva, escala, fondo o luz. Revisar también dos uniones en rojo/azul. Guardar respuesta literal separada y vinculada a los SHA, sin cambiar etiquetas históricas. Si hay ambigüedad, o la edición modifica otros rasgos importantes, el control es **inutilizable**: detener esta cohorte; no inventar etiquetas ni generar variantes hasta acertar.

Antes de consultar a los jueces, fijar sitios por imagen y región de la interrupción con inspección independiente de sus respuestas. El negativo necesita sus propios sitios; no transferir puntos mediante la identidad de la referencia. Coordenadas aproximadas, margen de dibujo estimado de3px como en la auditoría previa, sin certificado por píxel o confianza estadística. Conservar la interrupción como región revisada, no como una unión que deba contar el modelo. Si no se pueden delimitar claramente los sitios, la localización queda incierta.

## Consultas a los jueces

Máximo **seis consultas nuevas**: tres imágenes por modelo, orden rojo → azul → negativo; candidatos Qwen3.5-9B y Qwen3-VL-8B previamente fijados, uno cargado cada vez en el puerto propio8092. Son una nueva cohorte y no sustituyen outputs históricos. Runtime/weights/projectors actuales se verifican en ejecución; no nuevas dependencias, pesos o benchmarks.

Reutilizar `scripts/observe_visual_geometry.py` con `--location-profile docs/validation/isolated-mug-contacts-profile-2026-10-08.json`, y `scripts/visual_location_observations.py` sin cambios. Perfil, prompt y schema actuales se fijan por SHA; salida estructurada activada, temperature0, max_tokens512, timeout60s por consulta, context8192, reasoning off, image tokens1024–1536. Cero retries, rescates de JSON truncado, variantes de prompt, crops o cambio de presupuesto. La carga del servidor tiene el timeout90s del harness, separado del presupuesto de consultas. Parar la cohorte de ese modelo en el primer resultado inválido/no disponible; el otro modelo conserva su cohorte independiente.

Al finalizar la revisión humana, crear un plan nuevo válido para el harness con las tres rutas y SHA reales, comparaciones self/recolor/interrupted_attachment y orden fijado. El manifiesto de preparación no es ese plan ejecutable: el SHA del negativo y el registro humano aún no existen. El comando de ejecución pendiente es:

```powershell
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B scripts/observe_visual_geometry.py --plan docs/validation/mug-structural-control-reviewed-plan-2026-10-09.json --location-profile docs/validation/isolated-mug-contacts-profile-2026-10-08.json --model-repo 'unsloth/Qwen3.5-9B-GGUF' --output docs/validation/mug-structural-control-qwen35-2026-10-09.json --log-dir local_image_stack/experiments/bridge/target/mug-structural-control-qwen35-2026-10-09
```

Después, con8092 propio cerrado, mismo plan/perfil para `Qwen/Qwen3-VL-8B-Instruct-GGUF`, output/log-dir distintos `mug-structural-control-qwen3vl-2026-10-09`. No imprimir base64 ni enviar a los modelos nombres de casos, etiquetas, prompt de edición, criterios, coordenadas humanas o counts deseados: el harness envía únicamente pixels, target y definiciones actuales.

## Lectura predefinida de los resultados

1. Transporte/JSON inválido, truncado, reasoning o target incierto: **no disponible**, preservado; no convertirlo en fallo geométrico ni success.
2. Revisión previa de una imagen insuficiente: **control inutilizable/observación incierta**, no puntuar el juez contra una etiqueta inventada.
3. Positivos revisados: deben observar dos sitios con cajas separadas y evidencia correspondiente. Negativo revisado: una única unión superior; no contar la región inferior interrumpida como unión intacta.
4. Usar el criterio geométrico de la auditoría anterior: normalización continua x·width/1000, y·height/1000; una caja exclusiva por sitio, sin desplazar/clamp cajas. Disco contenido respalda localización condicional; solo intersección de borde la deja incierta; disco disjunto no respalda el sitio. Cajas que abarcan dos sitios, extras sin respaldo o conteos derivados solo de texto no prueban separación.
5. Conteo observado correcto sin localización respaldada: **señal parcial**, no éxito integral. Completar los tres casos con conteo y sitios respaldados da **éxito diagnóstico limitado a esta cohorte**. Fallar un positivo o no distinguir el negativo impide ese éxito. Comparador existente mantiene uncertain/admission false, sin cambio de gates.

Informar las tres filas de cada modelo, categorías y errores, sin tasa de accuracy extrapolada, identidad real, precisión de máscara o calibración. Un empate o éxito limitado no decide un juez universal: hacen falta controles estructurales adicionales y evaluación independiente. Ningún resultado habilita routing, rechazo automático, producción o vídeo completo.

## Verificación de esta preparación

El preflight offline verifica dos PNG originales por SHA/tamaño, fija15 bindings de fuentes/perfil, construye dos payloads positivos sin envío, comprueba que no incorporan etiquetas y que comparten prompt/schema, y confirma equivalencia del grafo Python con el `--dry-run` del binario existente, exit0/dispatch false. Presencia/tamaño de cuatro archivos de pesos y runtime es inventario, no rehash completo ni readiness GPU. Los SHA de texto describen bytes locales; Git puede normalizar finales de línea. Resultados en [preflight](validation/mug-structural-control-preflight-2026-10-09.json), [log](validation/mug-structural-control-preflight-2026-10-09.txt) y [cierre](validation/mug-structural-control-closing-checks-2026-10-09.json). Conservar el grafo dry-run ignorado en `local_image_stack/experiments/bridge/target/mug-structural-control-preparation-2026-10-09` junto a los originales al archivar.

Comprobación fresca de los contratos existentes, sin tests nuevos ni cambios de implementación:

```powershell
$env:MPT_RUN_INTEGRATION_TESTS = '0'
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_klein4b_graph.py test/test_visual_geometry_observations.py test/test_visual_location_observations.py test/test_retained_component_sites.py
```

**80 passed, 0,25s, Python exit0, sin warnings**; [log de esta fase](validation/mug-structural-control-tests-2026-10-09.txt). No certifican el negativo todavía inexistente, el servidor GPU ni la capacidad factual de los jueces. Health GET con timeout3s a las11:30:52UTC: 8080/8090/8188 no respondían; sin servicios iniciados/parados. Siguiente intervención: abrir únicamente ComfyUI8188, mantener8080 cerrado y GPU sin juego; después se solicita revisión del negativo antes de consultar a los jueces.
