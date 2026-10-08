# Segunda familia: geometría de tazas — 2026-10-08

Cinco observaciones Qwen3.5 completaron, sin timeouts. Los cuatro atributos categóricos fueron iguales en taza original, edición azul, dos estados con vapor y estado frío. No aparecieron avisos estructurales por color/vapor. **Esto no prueba identidad geométrica:** el inventario omite detalles y no hay negativo estructural de taza con revisión humana independiente.

Base ejecutada `b51e2b317119f5e0e4e818723fd9e511b083837b`, rama experimental limpia inicialmente.8080 ya cerrado, GPU891/12288MiB/3%/31°C, RAM20.23GiB libre;Comfy queue0/0. Se lanzó un servidor propio8092 y se cerró al terminar. Sin cambios a servicios compartidos, MPT estable, routing, workflows, pesos o dependencias.

## Generalización del observador

`scripts/observe_visual_geometry.py` acepta ahora `--plan`: target, imágenes únicas porSHA y comparaciones con provenance offline. Conserva el modo previo de llaves por defecto y el mismo schema/prompt de atributos. El target de esta prueba es ceramic mug, sin indicar color deseado, temperatura, label ni rol referencia/candidata. Validación rechaza target vacío, imagen/hash inválido, duplicados y referencias de comparación ausentes. Los metadatos de comparación no entran en los requests. Los health guards usan un socket nuevo para cada puerto.

[Plan/provenance](validation/mug-geometry-observation-plan-2026-10-08.json). Cinco imágenes originales completas, sin recortes/edición/generación. Pesos Qwen3.5-9B Q4_K_M/projectorF16 fijados y verificados, runtimeb11497;context8192,una slot,Flash Attentionon,reasoningoff,min1024/max1536 image tokens,max512 salida,temperatura0,timeout60s. Una carga y5 requests independientes; no diálogo entre imágenes y sin retries. [Respuestas brutas](validation/mug-geometry-observations-2026-10-08.json).

## Resultado y cobertura

Los cinco inventarios indican una abertura superior, cero muescas, cero collares y una unión genérica del asa al cuerpo. Describen color o vapor incidental en texto, pero la comparación no interpreta esas palabras como alteración física: solo usa valores categóricos/conteos. Requests5.664–6.484s,media6.008s; todosstop,reasoning_content vacío. No picoVRAM medido en este script, ni medición de generación de imágenes.

| Comparación | Papel del control | Hints / prioridad |
|---|---|---|
| Original consigo misma | Consistencia de software, mismoSHA | Ninguno / no_detected_signal |
| Original → azul | Cambio permitido de color, review previa del agente | Ninguno / no_detected_signal |
| Original → con vapor512 | Observación de estructura durante cambio de estado | Ninguno / no_detected_signal |
| Original → con vapor768 | Observación de estructura durante cambio de estado | Ninguno / no_detected_signal |
| Con vapor768 → frío768 | Separación geometría/estado | Ninguno / no_detected_signal |

Todas las comparacionesuncertain,no admisión/no rechazo automático. [Replay de prioridades](validation/mug-geometry-priority-replay-2026-10-08.json) usa [reviews vacías](validation/mug-geometry-review-inputs-2026-10-08.json): no se inventaron anotaciones humanas. Los labels históricos del dataset se refieren a tareas de color/estado; no se promueven a ground truth geométrico. El frío previamenteincierto sigueincierto como estado: este protocolo no confirma ausencia de vapor ni enfriamiento. Un autocontrol con el mismo inventario es tautológico para percepción; no contarlo como caso visual independiente adicional.

La inspección del agente de original/azul mantiene la revisión previa de forma similar, sin adjudicación humana nueva. El inventario no enumera el hueco delimitado por asa/cuerpo ni separa los dos contactos visibles del asa: cuenta solo boca y una unión genérica. Esto limita la cobertura; igualdad de cuatro atributos puede coexistir con diferencias de contorno/tamaño. No se corrige retroactivamente la respuesta del modelo ni se ajusta una etiqueta para obtener concordancia.

Falta un control de alteración estructural adjudicado de esta familia; no generar uno a partir de este informe ni afirmar sensibilidad/precisión. Esta prueba comprueba ejecución, ausencia de alarma por cambios no estructurales en estos artifacts y abstención de la política. No valida full video ni aprobación factual.

## Validación y siguiente tarea

92 tests offline pasan,exit0,2.83s ([log](validation/mug-geometry-observation-tests-2026-10-08.txt)):5 nuevos de plan/provenance/no label leakage +87 existentes. [Checks de cierre](validation/mug-geometry-closing-checks-2026-10-08.json): hashes/política verificados,5 requests/0generaciones,own8092 closed,Comfy/bridgealive,queue0/0,stable HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61/tracked tree intacto. Raw key observations/human labels unchanged; solo extensión del script experimental/tests/docs/evidencias. SHA final mediante historial/origin, no self-reference. Logs/modelos/copies ignorados deben conservarse antes de archivar el worktree.

Siguiente tarea concreta: añadir presencia explícita del target y cobertura de componentes observables antes de conectar estos inventarios al diagnóstico MPT; usar un artifact existente sin el target como control de ausencia, sin inventar un negativo de taza deformada. Mantener incertidumbre ante cobertura incompleta y todas las prioridades sin autoridad de admisión/rechazo. Cualquier futura evaluación de geometría grave necesita un negativo revisado independientemente. No cambiar modelos/routing para esconder una observación incompleta.
