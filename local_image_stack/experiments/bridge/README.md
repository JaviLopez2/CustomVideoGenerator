# Bridge experimental Klein 4B

Variante aislada, base MPT `f38c63e`. Reutiliza el snapshot de transformación/respuestas en `../../bridge/`, añade el snapshot WebSocket que faltaba y compila con el lockfile del checkout externo. No modifica `D:\Comfyui2Openai`, su configuración, binario, workflows ni servicio 8090. MIT upstream conservada en [LICENSE](LICENSE). El checkout externo contiene cambios locales: su HEAD por sí solo no describe el código; hashes y límites en la [procedencia](../../../docs/validation/flux-klein-4b-bridge-provenance-2026-10-07.json).

Aliases únicos de esta instancia: `flux-klein-4b-t2i-exp` y `flux-klein-4b-edit-exp`. Carga las dos plantillas del directorio `../workflows` y exige igualdad JSON con las compiladas; no toma workflows/configuración del servicio activo. El hook del snapshot se habilita mediante feature `klein4b_experiment`, activada por defecto solo en este crate. Los aliases legacy mantienen su ruta original; un test Rust verifica el tratamiento de prompt/seed legacy.

Contrato nativo: `model`, `prompt`, seed no negativo signed-64, tamaño divisible por 16 (máximo 16384 por dimensión), `n=1`, `steps=4`, `guidance=1`. Edit requiere 1–3 filenames Comfy relativos, contiguos y únicos en `reference_image`, `_2`, `_3`, más `reference_roles` ordenados. Admite los cuatro roles del contrato Python; no utiliza el campo legacy `style_reference_image`. Agrega las cláusulas de rol/raíz si no están ya en el prompt. Cuando se proporciona `temporal_progression=true`, requiere raíz y `temporal_state`, agrega el avance solicitado y rechaza las contradicciones explícitas cubiertas. No es un analizador semántico completo.

Cada referencia se escala/codifica y se encadena en ambos conditionings; no quedan slots demo/ausentes. Las sustituciones experimentales retornan antes del parche legacy para que no se sobrescriban bindings normalizados. No hay cambio de fallback ni de QA.

Desde el worktree principal, el agente puede ejecutar:

```powershell
cargo build --offline --locked --manifest-path local_image_stack/experiments/bridge/Cargo.toml --bin klein4b-experimental-bridge
cargo test --offline --locked --manifest-path local_image_stack/experiments/bridge/Cargo.toml --bin klein4b-experimental-bridge
$env:MPT_KLEIN_BRIDGE_BIN = Join-Path (Get-Location) 'local_image_stack\experiments\bridge\target\debug\klein4b-experimental-bridge.exe'
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_klein4b_rust_bridge.py
```

Binario local ignorado por Git. Toolchain observado: Rust/Cargo 1.98.1. Dependencias resueltas offline y locked; no se descargaron ni modificaron dependencias globales. Quedan seis warnings `dead_code` del snapshot WebSocket, que esta instancia no inicializa. No se alteró ese código para ocultarlos.

Modos del binario:

- `--dry-run FILE`: transforma un JSON de intención y devuelve `comfy_request` + `dispatch_allowed=false`; sin HTTP ni envío a Comfy.
- `--serve-preview`: escucha solo en `127.0.0.1:8091`. GET `/health` y `/v1/models`; POST `/experimental/preview` transforma sin dispatch; `/v1/images/*` responde 403. El test arranca y termina únicamente su propio proceso, con ventana oculta en Windows y comprobando que el puerto esté libre.
- `--serve-gpu`: modo implementado para una futura prueba expresamente autorizada, **no ejecutado en esta fase**. Mismo puerto aislado y backend `127.0.0.1:8188`, solo `/v1/images/generations` nativo; usa polling, sin WebSocket. Habilita envío real a Comfy. No usarlo por iniciativa propia ni apuntar MPT estable a esta instancia.

Para convertir un envelope de `build_request`/`prepare_graph` al JSON del bridge, copiar su `payload` y añadir su lista lateral `reference_roles`; el test contiene esa serialización. Un caller de intención cruda puede añadir los campos temporales. No enviar el envelope completo ni considerar `dispatch_allowed=false` una propiedad del endpoint de generación cuando se habilite GPU.

Resultados finales: 173 tests Python en suite ampliada (22 casos nativos) y 1 Rust, todos aprobados. Tests actuales Qwen/continuidad sin modificar. CLI T2I/Edit/temporal produce el mismo JSON que el adaptador Python; preview HTTP y bloqueo 403 comprobados. Logs en `docs/validation/flux-klein-4b-bridge-*-2026-10-07.txt`. El log native-tests registra el paso intermedio de 19 casos; la suite combinada final contiene los guards adicionales y 22 casos nativos. No se ejecutó inferencia.

Pendiente: activar esta instancia solo para una prueba GPU mínima autorizada, fijar revisión/hash del binario efectivo, revalidar assets/inventario y registrar memoria/tiempo/OOM. Después adaptar el caller MPT experimental a roles y endpoint 8091 para escena/smoke aislados; no basta cambiar el alias del caller actual si no manda roles. El candidato sigue `planned`, sin promoción.
