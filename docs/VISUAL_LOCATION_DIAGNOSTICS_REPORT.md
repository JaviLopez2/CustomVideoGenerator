# Ubicaciones visuales y contraste de candidatos — 2026-10-08

Las coordenadas hacen inspeccionables los errores, pero **no resuelven la fiabilidad del juez**. Qwen3.5 separa dos contactos y desplaza varias cajas; Qwen3-VL localiza mejor el borde de esta taza, pero omite el hueco del asa y agrupa contactos. Ninguno se habilita para aprobar geometría, identidad o escenas.

Base `fe63c61dcf09bd1e6ec50dd3e43ac415d1f99ada`, mismo worktree/rama experimental. Continúa el [contraste de formato](COMPONENT_DECODING_DIAGNOSTICS_REPORT.md), cuyo checkpoint ya está publicado. Este nuevo código se ejecutó sin commit sobre esa base; raw reports registran hashes reales de harness/módulo/profile/plan. SHA final de cierre mediante historia/origin; no confundirlo con la base.

## Protocolo y pruebas de software

Nuevo `scripts/visual_location_observations.py`, versión `target-location-observations-1`, seleccionable mediante `--location-profile` en el observer. Conserva protocolos anteriores/defaults. Cada sitio declarado lleva box `[left,top,right,bottom]`, enteros normalizados 0–1000 sobre la imagen completa y evidencia breve. El prompt/schema explica estados/tipos, no aporta cantidades deseadas, roles, labels o una respuesta ejemplo. Applicability conserva present/absent/uncertain y not_applicable según target.

Validación rechaza coordenadas fuera de rango, bool/float, cajas vacías/invertidas, duplicados exactos por componente y contradicciones estructurales de estados. No clampa, completa o repara respuestas. Se calcula IoU entre regiones del mismo componente; cualquier solapamiento positivo produce un hint de revisión, sin merge ni rechazo. Cajas contiguas, perspectivas distintas o solapamientos no demuestran por sí mismos identidad/deformación. El conteo es de entradas de región, no una medición de verdad física. `pixel_truth_verified=false` permanece siempre.

El adaptador de diagnóstico acepta esta versión explícita conservando las mismas prohibiciones de admisión/rechazo. No cambia el caller/QA ni activa config/UI/planner; sigue requiriendo store inyectado. `--model-repo` del harness admite únicamente los dos candidatos previamente fijados y descargados en el manifiesto, con default Qwen3.5-9B; no resuelve modelos nuevos ni modifica routing MPT.

## Controles retenidos, iguales límites

[Profile](validation/mug-visual-location-profile-2026-10-08.json), [plan](validation/mug-visual-location-plan-2026-10-08.json): taza roja original, variante azul y ausencia de taza en reloj/llave. No negativo de taza deformada ni nueva adjudicación humana de su geometría. Los dos modelos usan el mismo prompt/píxeles/schema/temperatura 0/max512/timeout60 y runtime b11497/context8192/slot1/Flash Attention on/1024–1536 visual tokens/thinking off. SHA de pesos/projectores verificados; sin descargas. Servidor 8092 nuevo por modelo, terminado solo por PID propio. Fingerprints permiten comprobar igualdad de las dos requests que ambos intentaron.

| Candidato local | Requests reales | Resultado observado |
|---|---:|---|
| Qwen3.5-9B Q4_K_M/F16 | 2 | Roja completa 11,174s: una boca, un hueco del asa, dos contactos, un borde. Azul 11,648s: finish_reason=length, 512 tokens, JSON incompleto; unavailable. Tercera no ejecutada. |
| Qwen3-VL-8B Q4_K_M/F16 | 3 | Completas 7,656 / 7,240 / 5,133s, stop/0reasoning. Presencia correcta en las dos tazas y ausencia correcta en reloj/llave; hueco del asa absent incorrectamente en ambas, contactos agregados en una caja. |

[Raw Qwen3.5](validation/mug-visual-location-observations-2026-10-08.json) conserva la truncación y corta sin retries. No se añade una llave JSON faltante, se amplía presupuesto o se vuelve a solicitar una respuesta favorable. El autocontrol rojo queda uncertain; azul/ausencia unavailable por evidencia no completada/no ejecutada.

[Raw Qwen3-VL](validation/mug-visual-location-qwen3vl8b-2026-10-08.json) conserva todos los errores semánticos. En roja, una caja de contactos afirma dos puntos; en azul, una caja dice uno. Sus conteos de entradas son iguales, por lo que no aparecen hints de diferencias entre tazas. Eso no acredita igualdad física. Ausencia comparada queda unavailable/target_not_established. No se mezclan estos resultados con los anteriores del contrato de QA, donde Qwen3-VL fue peor en detección de defectos.

La inspección visual de esta sesión del PNG rojo original confirma que varias cajas de Qwen3.5 quedan desplazadas hacia arriba/izquierda respecto a las regiones que describen: la caja de boca termina aproximadamente antes del borde visible, y los contactos no quedan centrados en las uniones. Qwen3-VL encuadra mejor el borde en este ejemplo, pero su caja de contactos abarca una región amplia y niega un hueco claramente visible. Esto es revisión cualitativa del asistente, no anotación gold independiente, métrica IoU contra ground truth ni nueva respuesta del usuario.

Una muestra positiva, una variante y una ausencia no validan sensibilidad a deformaciones ni tolerancias de producción. Latencias son mediciones locales por request; longitudes de salida y resultados difieren. No se mide un nuevo pico GPU ni se infiere capacidad/throughput de una prueba completa de vídeo. Total de esta fase **5 requests VLM, 0 generaciones, 0 retries**; ambas instancias propias cerradas. Sumadas al checkpoint precedente: **16 requests en esta continuación, 0 generaciones**. No nuevos modelos, deps, workflows o servicios compartidos cambiados.

## Diagramas y replay offline

`scripts/render_visual_location_overlays.py` genera SVG de revisión: embebe bytes originales intactos, convierte boxes normalizadas a dimensiones originales, dibuja regiones y leyenda. Usa XML escapado; no generación ni modificación del raster fuente. Verifica profile/report/pixel hashes y conserva destinos existentes. Los diagramas, PNG originales y logs están en target ignorado, no se publican sus bytes.

Diagramas locales de la taza roja: [Qwen3.5](../local_image_stack/experiments/bridge/target/mug-visual-location-overlays-final-2026-10-08/16c94d6f649e6934.svg), [Qwen3-VL](../local_image_stack/experiments/bridge/target/mug-visual-location-qwen3vl8b-overlays-2026-10-08/16c94d6f649e6934.svg). También se guarda SVG de azul y ausencia para Qwen3-VL; el azul truncado de Qwen3.5 no se transforma en un diagrama validado. El primer directorio de overlays se conserva; la revisión final de altura de leyenda produjo el mismo SVG de roja, con hash igual y código/index distintos. Abrir en Codex quedó queued; no se afirma que el usuario ya los haya visto.

[Replay Qwen3.5](validation/mug-visual-location-diagnostic-replay-2026-10-08.json) y [Qwen3-VL](validation/mug-visual-location-qwen3vl8b-replay-2026-10-08.json): tres vinculaciones cada uno, 0 inferencias. Truncado y no ejecutado permanecen unavailable; respuestas completadas son uncertain de disponibilidad registrada, no verdad perceptual. Los labels originales y la anotación A/B/C no se modifican.

## Validación, cierre y pendiente real

**520 tests +17 subtests pasan, 1 integración omitida**, exit0, 17,04s: [log final](validation/visual-location-candidates-final-tests-2026-10-08.txt). Repetir el conjunto de 20 archivos del informe anterior, añadiendo `test/test_visual_location_observations.py`, con los mismos env vars/Python portable. Son 25 casos nuevos sobre los 495 previos: 23 de coordenadas, 1 del adaptador y 1 del selector. Logs171/42 y519 pertenecen a subconjuntos/revisiones anteriores; todos conservados. Warning Starlette/httpx existente; sin dependencias nuevas.

[Checks de cierre](validation/visual-location-closing-checks-2026-10-08.json): JSON/AST/hashes, igualdad de payloads comparables, modelo/runtime y logs, XML y bytes originales embebidos, report/replay provenance, secretos sin imprimir coincidencias, servicios y stable protegido. Diff/staged check revisados antes de commit y push normal; stable HEAD/tracked se mantienen en `6d27ba4963ffe469d635db71eaeec506a8ff4b61`. El metadata Git compartido se usa únicamente para refs del experimento. No permiso permanente inferido de escalaciones específicas.

El bloqueo de una prueba completa con admisión automática es la fiabilidad perceptual, no acceso local: coordenadas válidas/JSON completo no prueban partes correctas. **Siguiente tarea concreta:** evaluar un componente por request con evidencia breve y regiones revisadas independientemente sobre estos mismos artifacts; validar separación y presencia antes de combinar resultados o aumentar presupuesto. Conservar fallos y Qwen3.5 como candidato experimental general, sin promoción de ninguno. Un modelo/localizador nuevo que requiera pesos/deps necesita autorización específica; no forzar una decisión QA favorable ni generar más imágenes para ocultar el problema.
