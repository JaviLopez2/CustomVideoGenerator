# Edición local de la taza con máscara — preparación, 2026-10-09

Desde `903e68a1049e24e76c859fc1e2cce95488f39153`, la nueva preparación queda completa **a nivel de grafo e interfaces**, con región revisada por el usuario y ejecución pendiente. La edición anterior sin separación real permanece descartada. [Protocolo fijado](validation/mug-masked-protocol-2026-10-09.json), [grafo aislado](validation/mug-masked-prepared-graph-2026-10-09.json), [contratos locales](validation/mug-masked-node-contracts-2026-10-09.json), [traza de fuente](validation/mug-masked-interface-preflight-2026-10-09.json).

## Ruta y límites de compatibilidad

El constructor nuevo `local_image_stack/experiments/klein4b_masked.py` reutiliza `prepare_graph` y su binding verificado del experimento Klein4B, una referencia roja `identity_reference`, conditioning positivo/negativo y escalado de referencia1MP anteriores. No registra aliases ni cambia plantillas compiladas del bridge, modelos, defaults de MPT o archivos de ComfyUI. Solo cambia el latente objetivo y la salida final del grafo nuevo:

- Nodo10 pasa de EmptyFlux2LatentImage a VAEEncodeForInpaint, imagen original512², VAE Flux.2 actual, máscara de nodo30 y grow_mask_by0. La fuente local obtiene el downscale del VAE, neutraliza el interior de la máscara y devuelve LATENT con noise_mask.
- Nodo30 LoadImageMask lee el canal rojo de un PNG L512² binario, blanco255=editable/negro0=protegido. Evita la inversión del canal alpha. La máscara no se añade como otra referencia al modelo.
- SamplerCustomAdvanced11 ya consume noise_mask y lo pasa al guider; no se modifica el sampler ni se añade conditioning de un modelo inpainting distinto.
- Nodo31 ImageCompositeMasked toma el original como destination, el resultado decodificado como source y la misma máscara, x/y0/resize_source false. SaveImage13 guarda solo ese resultado. Es una conservación de píxeles, no prueba de identidad física.

20 nodos y26 enlaces pasan checks de tipos, puertos, inputs requeridos y ciclos contra contratos de `/object_info`;19 clases distintas. La traza usa los bytes locales por SHA de nodes.py, nodes_custom_sampler.py, nodes_mask.py y nodes_flux.py sin importarlos, cargar torch/modelos o ejecutarlos. La [fuente oficial del sampler](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_custom_sampler.py), [composición](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_mask.py) y [guía oficial Klein](https://docs.comfy.org/tutorials/flux/flux-2-klein) respaldan las interfaces y la edición genérica; no se encontró allí certificación de esta tarea de inpainting ni de su calidad en la3060. La implementación local, que puede diferir de master, está fijada en el preflight.

Esto acredita una ruta estructural compatible con máscara genérica. **No acredita ejecución del VAE/modelo, dimensiones reales de tensores, éxito del corte, VRAM máxima o admisión de archivos Comfy.** La prueba mínima GPU seguirá siendo necesaria. El futuro resultado debe pasar el verificador exacto de píxeles fuera de máscara; las máscaras latentes pueden remuestrearse y la conservación se comprueba en el PNG final, sin asumir que el sampler mantiene cada píxel. Ningún nuevo peso, custom node o dependencia fue necesario para preparar esta ruta.

El envelope omite deliberadamente `payload` del bridge legacy: enviarlo ejecutaría una edición sin máscara. Tiene dispatch_allowed false/runtime_validated false. La ejecución futura usará un único POST directo al Comfy compartido8188 con el grafo fijado, seguido de polling; no arranca8091/8090 ni cambia su configuración. El constructor no envía HTTP.

## Región revisada y evidencia visual

Fuente roja SHA `16c94d6f649e693492a47a39a48e35f0ccede34f060c4e9031e385accf10ec93`, original intacto. Máscara L512²,1215 píxeles blancos (~0,46% del frame), bounds exclusivos `[323,335,360,374]`. [Vértices, PNG/SVG y hashes](validation/mug-masked-region-draft-2026-10-09.json). Cubre el disco aproximado3px del punto inferior338,354; el entorno65×65 del superior347,222 permanece negro. Es región de trabajo, no anotación certificada del objeto.

El usuario revisó el [tablero](D:/Apps/MPT-worktrees/image-model-routing-modernization/local_image_stack/experiments/bridge/target/mug-masked-preparation-2026-10-09/mask-region-review.png) y responde literalmente **«La zona cian es adecuada»**. [Revisión independiente de región](validation/mug-masked-region-human-review-2026-10-09.json) vinculada a source/mask/PNG/draft por SHA. Solo revisa la región; no aprueba un negativo todavía inexistente, counts de positivos, correspondencia física, gold por píxel, un juez o producción.

Mask/PNG/SVG se crean en el directorio ignorado `target/mug-masked-preparation-2026-10-09`, sin modificar la foto. SVG incrusta bytes originales y se renderiza con Node/sharp existentes; exit0, avisos Fontconfig de caché externa no escribible, sin cambio de permisos/configuración. PNG revisado visualmente por el asistente y el usuario. Conservar estos assets al archivar, junto a originales, máscara y controles anteriores. Máscara aún no copiada a input de Comfy; el grafo todavía no fue admitido/encolado.

El verificador de conservación se probó también sobre la edición anterior retenida:259939 píxeles fuera de esta máscara presentan alguna diferencia exacta y1200 dentro. Son diferencias RGB de cualquier magnitud, **no distancia perceptual, porcentaje de deformación o score de identidad**. La edición anterior ya se descartó por la observación humana de ausencia de corte; este cálculo no cambia esa etiqueta ni evalúa un juez.

## Tests reales y cambios

26 tests nuevos verifican aislamiento del grafo, ausencia del payload que despacharía sin máscara, orden/ref conditioning, filenames/seed, dirección de máscara, tipos/puertos/ciclos, máscaras inválidas y conservación/detección de deriva mediante fixtures sintéticos. RED26 fallos NotImplemented antes de implementación; GREEN26 pass con9 avisos Pillow getdata deprecated. Se sustituyó esa lectura por NumPy existente, sin depender de una nueva API. [RED](validation/mug-masked-red-tests-2026-10-09.txt), [GREEN inicial](validation/mug-masked-green-tests-2026-10-09.txt).

```powershell
$env:MPT_RUN_INTEGRATION_TESTS = '0'
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_klein4b_masked.py test/test_klein4b_graph.py test/test_klein4b_experiment.py test/test_visual_location_observations.py test/test_retained_component_sites.py
```

**112 passed,0,54s,Python exit0,sin warnings**, [log fresco](validation/mug-masked-final-tests-2026-10-09.txt); prueban contratos offline, no GPU. Tests previos preservados. [Comprobaciones finales](validation/mug-masked-closing-checks-2026-10-09.json) vinculan grafo/máscara/revisión/fuentes, JSON, scope y diff. 0 nuevas generaciones/VLM/benchmarks/descargas/servicios iniciados/parados o cambios app/jueces/routing/gates/deps/modelos/plantillas activas/estable. Se añaden módulo/test aislados y un nuevo grafo documental del experimento; los workflows existentes permanecen intactos.

## Siguiente tarea concreta

Una única edición enmascarada512²/4pasos/seed42/guidance1,0reintentos. Primero revalidar assets, recursos, cola y source/input; copiar la máscara PNG al nombre fijado por escalación específica, sin sobrescribir archivos distintos. Verificar que el fuente sigue512²/RGB y la máscara512²/L/binaria; registrar grafo/prompt_id y resultado. Un timeout deja potencialmente vivo el job; inspeccionar su historial sin reenviar ni cancelar trabajos ajenos.

Después comprobar exactitud fuera de máscara, cambio dentro, éxito técnico y PNG alineado. Solicitar al usuario revisión del hueco inferior y unión superior intacta; si falla alguno, descartar el control y cerrar sin judges/reintentos. Solo con negativo válido y counts positivos revisados, preparar plan real de3imágenes y hasta6 consultas a los dos jueces actuales. No convertir aprobación de región en certificación del resultado, y no promover candidatos.
