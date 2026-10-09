# Evidencia visual temporal retenida — preparación 2026-10-09

Base `cc98f6e4f10cd49b54806856d2f6403654b5aa21`, mismo worktree/rama experimental, inicio limpio y diez worktrees comprobados. Se inspeccionan los cuatro originales que forman los tres pares temporales ya existentes; cero nueva inferencia, generación o descarga.

## Lo que muestran las imágenes

[Plan fijado antes de revisar](validation/retained-temporal-visual-input-plan-2026-10-09.json). Inspección directa del asistente mediante `view_image`, resolución original. Los labels históricos ya se conocían; esta revisión no es ciega ni gold humano. Se conservan el dataset, los captions/OD, contratos y labels históricos por SHA.

| Fotograma | Pista visible en la inspección del asistente | Límite |
|---|---|---|
| Referencia 512 | No veo una columna pálida evidente sobre la abertura | No certifica ausencia física global; interior oscuro |
| Cálido 512 | Formas translúcidas que suben desde la abertura | Se prolongan fuera del borde superior; no acreditan causa química o temperatura |
| Caliente 768 | Columna grande de formas parecidas a vapor sobre la abertura | Encuadre/escala distintos de la referencia; no prueba identidad física |
| Enfriado 768 | No veo una columna comparable, pero hay formas/reflejos ambiguos en la abertura oscura | Luz azul no demuestra té frío, ausencia completa de vapor o líquido inmóvil |

[Auditoría ligada a cada fuente](validation/retained-temporal-assistant-visual-audit-2026-10-09.json). Los tres QA archivados siguen uncertain según el replay v4 anterior; **no se vuelven a ejecutar ni se reetiquetan**. La mención smoke en captions no se sustituye por steam para obtener pass. Una superficie que parezca lisa en una imagen estática tampoco mide movimiento, calor o enfriamiento.

## Inputs completos preparados

Los recortes de forma de la taza eliminan el contexto sobre la abertura donde aparecen las columnas visibles. Se preparan cuatro **fotogramas completos**, margen0, mismo modo RGB/dimensiones/valores de píxel; metadata auxiliar retirada. Dos son512×512 y dos768×1376. No se usa máscara, resize, recolor o reconstrucción del contenido. Conservar el área capturada completa tampoco recupera lo que ya corta la cámara en el borde superior.

Se reutiliza `prepare_visual_regions.py` sin modificarlo. [Receta congelada](validation/retained-temporal-fullframes-recipe-2026-10-09.py) ejecutada con Python MPT `-I -B`, exit0; cuatro comparaciones independientes de arrays NumPy verifican exactamente píxeles/modo/dimensiones y metadata vacía. [Resultado y bindings](validation/retained-temporal-fullframes-result-2026-10-09.json). Fuente/helper/plan/legacy/replay/manifiesto ligados por SHA, sin sobrescribir archivos. El manifiesto solo certifica cobertura del rectángulo completo de imagen; revisión humana semántica pendiente y flags de admisión/identidad false.

Artifacts ignorados en `local_image_stack/experiments/bridge/target/retained-temporal-fullframes-2026-10-09`: cuatro PNG y manifiesto. Conservarlos junto a originales. Esta fase no modifica el código del helper/runner/QA; los116 tests del checkpoint anterior son históricos. La prueba fresca es la ejecución de la receta, arrays, hashes y revisión de protocolo; no se inventa otro run de pytest.

## Método siguiente fijado

[Diseño](validation/pairwise-visible-cue-design-2026-10-09.json): observador genérico parametrizado por sujeto y una descripción de pista visible; mismo prompt/schema para todos los pares. Imagen1 anterior, imagen2 actual. Seis campos: presencia, visibilidad de pista y evidencia breve para cada fotograma. Visibilidad observed/not_observed/uncertain; not_observed se limita al área visible y no prueba ausencia física global. Área oscura/oculta/ambigua o sujeto no establecido requiere uncertain. La pista elegida aquí son formas pálidas parecidas a vapor junto a la abertura, separadas de su causa física.

Tres pares temporales conservados más referencia/referencia idéntica por construcción. **Máximo8 solicitudes,4 por cada uno de los dos jueces existentes**, secuenciales,8192contexto/256tokens/temperature0/sin thinking;0retry/generación/descarga. Es un presupuesto nuevo previo a ejecución, no extensión de la cohorte de seis consultas ya cerrada. La consistencia de bytes no da gold de presencia/ausencia de la pista. Contradicción entre categorías de inputs idénticos se conserva como inconsistencia y detiene esa cohorte, sin hint de transición ni rescate por prompt/tokens.

Cambio de visibilidad es un hint categórico. `identity_score`, `state_score` y `progression_score` permanecerán separados y null; verdictuncertain, sin admisión/rechazo automático. No evalúa el requisito completo de still liquid ni temperatura, y no transforma el hint en prueba de identidad/progresión física o pass temporal. El modelo no recibe labels/captions/estado deseado, ids de casos o expectativas históricas. Revisión independiente del protocolo sin hallazgos; aclaración explícita de consistencia antes de implementación/inferencia.

Próximo trabajo autónomo: implementar/probar observador y runner reutilizando proceso/runtime/modelos/preflight existentes; fijar plan ejecutable/codeSHA, volver a comprobar recursos/cola y ejecutar una cohorte por modelo. Preservar todas las respuestas y omisiones; comparar con inspección del asistente sin inventar precisión humana. Producción/defaults/gates/routing/deps/modelos/servicios/estable intactos. [Cierre](validation/retained-temporal-visual-input-closing-checks-2026-10-09.json). No hace falta abrir8080 ni intervención para la preparación CPU siguiente.
