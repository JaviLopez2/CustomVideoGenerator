# Klein 4B: verificación de assets y plan de instalación

Fecha: 2026-10-07. Base de preparación `57a5747016c1c4b4109860cb0b696edab9eabc75`. La preparación solo leyó el encoder y metadatos públicos. La instalación posterior autorizada sobre `99d6abd` se detalla al final. Evidencia previa: [preflight JSON](validation/flux-klein-4b-asset-preflight-2026-10-07.json); fuentes fijadas por revisión y hashes completos en el [manifiesto](validation/flux-klein-4b-assets.json).

## Resultado observado

Encoder local: `C:\Users\JAVIER\ComfyUI-Installs\ComfyUI\ComfyUI\models\text_encoders\qwen_3_4b.safetensors`. Tamaño **8.044.982.048 bytes** y SHA-256 **`6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a`**, ambos iguales al LFS publicado por Comfy-Org/z_image_turbo en revisión `6fc90a3b1b653e935a0d175e260736de25b84df5`. Cabecera Safetensors: 398 tensores BF16 y offsets contiguos que cubren el archivo; tamaño y mtime no cambiaron durante el hash. No se importó Torch ni se cargaron tensores.

Esto verifica identidad con esa distribución, no el historial original de descarga ni ejecución en ComfyUI. El manifiesto marca únicamente este componente como `verified_local_bytes`. DiT/VAE conservan `sha256=null`; sus `expected_sha256` proceden de metadatos remotos y no de una descarga o medición local. El candidato completo sigue `planned`.

Licencia publicada: [Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) y la distribución Comfy-Org del encoder declaran Apache 2.0; [Klein 4B FP8](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8) también. Para el VAE, la etiqueta `other` de Comfy-Org/flux2-dev describe la tarjeta del repositorio y no basta para determinar la licencia del componente. [BFL declara Apache 2.0 para el autoencoder FLUX.2](https://github.com/black-forest-labs/flux2#flux2-autoencoder). El LFS publicado de `flux2-vae.safetensors` coincide exactamente en SHA y tamaño con `vae/diffusion_pytorch_model.safetensors` de BFL/FLUX.2-dev, revisión `26afe3a78bb242c0a8bb181dcc8937bb16e5c66c`; es distinto del archivo `ae.safetensors`. No se trasladan al DiT dev ni al Klein 9B los permisos de este VAE.

## Instalación futura propuesta

Raíz de destino: `C:\Users\JAVIER\ComfyUI-Installs\ComfyUI\ComfyUI\models`. No se escribirá en MPT estable ni se reemplazará el encoder existente.

| Componente | Destino relativo | Bytes publicados | Acción pendiente |
| --- | --- | ---: | --- |
| DiT 4B Distilled FP8 | `diffusion_models\flux-2-klein-4b-fp8.safetensors` | 4.070.624.520 | Descargar desde BFL, revisión fijada `5b4408e59397a4a37ccb46afe426d8ed86379441` |
| VAE Flux2 | `vae\flux2-vae.safetensors` | 336.213.556 | Descargar desde Comfy-Org/flux2-dev, revisión fijada `ed33133cd56476eac818c0943b6f9419b3e4a3a1` |
| Encoder Qwen3-4B BF16 | `text_encoders\qwen_3_4b.safetensors` | 8.044.982.048 | Reutilizar el archivo verificado; no descargar otra copia |

Descarga adicional total: **4.406.838.076 bytes**, aproximadamente **4,41 GB / 4,10 GiB**. GET de metadatos y comprobación local confirman que los dos destinos faltan. Snapshot de espacio libre: C **135.394.729.984 bytes**, D **136.050.946.048 bytes**; volver a comprobar antes de descargar. Estas cifras son disco, no presupuesto de VRAM; el encoder BF16 de unos 8 GB no demuestra que todo el workflow quepa en 12 GB.

Secuencia de instalación, todavía no ejecutada:

1. Obtener autorización específica para descargar solo esos dos archivos y escribirlos en las dos rutas Comfy indicadas. Usar escalaciones específicas para acceso fuera del worktree; no cambiar permisos globales. No incluye activación de aliases, reinicios, dependencias o GPU.
2. Volver a comprobar destinos, espacio, hashes fijados y encoder. Si aparece un archivo preexistente, leer/hashar y conservarlo; no sobrescribir una discrepancia automáticamente.
3. Descargar cada fuente HTTPS fijada del manifiesto a un archivo parcial adyacente, fuera de Git. Conservar progreso y errores sin URLs firmadas, credenciales ni tokens en logs. Detenerse si el proveedor exige autenticación o la identidad no coincide; no resolver mediante otro modelo/variante.
4. Comprobar bytes, SHA-256 esperado y estructura Safetensors antes de renombrar cada parcial al nombre definitivo. Registrar el hash local real y la procedencia en un nuevo checkpoint. Un partial o hash remoto no se admite como asset instalado/verificado.
5. Comprobar inventario local y loaders por GET. Si hace falta refrescar/reiniciar un servicio, acordar ese paso explícitamente. Conservar `planned`: assets presentes no certifican integración ni generación.

## Lo que sigue después de instalar

Preparar integración experimental aislada del bridge, con aliases nuevos y materialización por solicitud o variantes por número de referencias. El bridge actual no expande cadenas Flux ni aplica steps/CFG del payload: copiar el template Edit estático no basta. Fijar revisiones de los procesos efectivos, no solo HEAD de sus carpetas. No modificar el significado de `flux-klein-precision` ni fallback/QA productivos.

Con autorización específica de GPU: load y T2I mínimo, single-ref, continuidad temporal y 2–3 refs; luego escena MPT aislada y smoke de dos escenas mediante Factory con root/branch experimental, publicación desactivada y logs/artifacts separados. Empezar con resolución pequeña y dejar la resolución objetivo como gate posterior; medir estabilidad/OOM, tiempo, VRAM y repetibilidad, conservar identidad y exigir avance de estado. Sin benchmarks generales, vídeo completo inicial ni promoción automática. La prueba mínima y la prueba de extremo a extremo son fases distintas.

## Verificación de este checkpoint

Contratos afectados por el manifiesto: **39 passed**, [log](validation/flux-klein-4b-asset-preflight-tests-2026-10-07.txt). El test experimental de aislamiento admite que solo el encoder tenga hash verificado y exige DiT/VAE pendientes y candidato `planned`. No se modificaron tests históricos de Qwen/continuidad ni código de aplicación. Los **151 passed** del checkpoint anterior son evidencia histórica, no una ejecución nueva en esta fase.

Revisión de JSON, hashes de grafos, referencias locales, secretos por patrones y diff antes de publicar. Sin descargas de pesos, cambios de dependencias, servicios, routing, bridge, grafos, generación o GPU.

## Ejecución autorizada: assets instalados

El usuario autorizó descargar/verificar DiT y VAE y permitió considerar otro encoder si resultase mejor. Se conservó Qwen3-4B BF16: es el archivo del contrato y coincide con la distribución oficial verificada. No hay mediciones locales de memoria/calidad que justifiquen reemplazarlo. Mantener esta base permite evaluar primero el candidato definido; una eventual alternativa de encoder requerirá evidencia de necesidad y comparación concreta.

Base `99d6abddf6ea525f040ac1d0d881f88184950bef`. DiT y VAE descargados desde las revisiones fijadas a parciales, verificados por tamaño/SHA-256/cabecera y renombrados a los destinos del plan sin reemplazar archivos existentes. Total **4.406.838.076 bytes**. Encoder rehashado y sin cambios. DiT: 309 tensores (F32/BF16/F8_E4M3); VAE: 251 tensores (F32/I64); offsets contiguos y ajustados al tamaño de cada archivo. Estos checks no cargan tensores ni prueban compatibilidad de ejecución.

Los tres componentes quedan `verified_local_bytes`, con hash local real y evidencia en el manifiesto. Candidato completo sigue `planned`: revisiones de ejecución, integración y gates GPU pendientes. [Registro de instalación](validation/flux-klein-4b-install-2026-10-07.json). No se guardaron pesos dentro de Git, credenciales ni URLs firmadas.

GET `/object_info` posterior no se pudo completar: conexión rechazada en `127.0.0.1:8188`, WinError 10061. No se afirma que los loaders hayan actualizado el inventario; no se inició/reinició ComfyUI. Contratos afectados: **39 passed**, [log](validation/flux-klein-4b-install-tests-2026-10-07.txt). Sin cambios de dependencias, routing, grafos, bridge ni generación/GPU. La copia estable permanece intacta.

Siguiente fase: preparar integración experimental y recuperar el servicio para validar su inventario. Iniciar/reiniciar ComfyUI y ejecutar GPU quedan fuera de la autorización de descarga; necesitan encargo específico. No sustituir `flux-klein-precision` ni promover el candidato por tener los archivos instalados.
