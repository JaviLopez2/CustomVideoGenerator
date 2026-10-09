# QA visual local: resultados y límites — 2026-10-08

## Actualización — parser temporal v3, 2026-10-09

[Parche y prueba](TEMPORAL_CAPTION_AMBIGUITY_REPORT.md), base417dac3: cualificación/contradicción léxica relevante se conserva uncertain, con ambiguous_evidence y score null; evidencia anterior ambigua no acredita progreso. Violación inequívoca y omisión conservan fail/uncertain, sin inferir identidad. VERSIONvisual-qa-3 invalida keys v2; no nueva capa de caché.37 casos nuevos/186 tests finales pasan6,55s/exit0/sin avisos; revisión detectó salto de línea, cuatro RED antes de corrección y revisión final sin hallazgos.0 inferencia/generación/GPU/descargas/servicios/modelos/defaults/gates/routing/deps/estable. Sigue siendo parser léxico inglés limitado, sin solución universal de negación ni validación de fidelidad visual. Próximo replay CPU de captions/contratos guardados v2/v3 antes de más consultas. Los resultados históricos siguientes no se reescriben como v3.

El camino local nuevo tarda **4,51s de media**, pero decide solo **3 de 16 casos**. Los otros 13 quedan inciertos y el pipeline experimental los rechaza. No está demostrado un QA fiable de partes pequeñas, fusión, identidad factual o progresión temporal. **No activar routing automático ni promover Klein.** Esta fase reduce el coste, conserva evidencia y descubre el siguiente bloqueo; no completa la validación semántica.

## Estado, alcance y evidencia

Inicio limpio en `D:\Apps\MPT-worktrees\image-model-routing-modernization`, rama `factory/image-model-routing-modernization`, HEAD local/remoto `87c7ba568b19ed48d041b625f269f5112f0ef4fd`. Se verificaron worktrees, instrucciones y handoffs; fetch mostró 0/0 divergencia. Checkpoints: `1ec050a9b5dc2268dbf5a501b4b4fb663c659019` (dataset/auditoría), `d8de6a5195eecb6db6e242736fc4d5e89509d0ab` (implementación/tests). Identificar el commit final de informe/evidencias mediante `git log -1 -- docs/VISUAL_QA_REPORT.md`; no incrustar un SHA autorreferente.

[Dataset ligero](validation/visual-qa-dataset-2026-10-08.json): 16 imágenes ya guardadas, 9 positivas, 6 defectuosas y 1 estado frío incierto. Incluye paths, hashes SHA256, modelo, seed, prompt, referencias/roles, sujeto, contratos de cantidad/geometría/estado, estado anterior, verdict esperado y motivo. Cubre tejido, eliminación de texto, identidad/estilo con orden invertido, llave deformada/fusionada, agujas adicionales, temporal caliente/frío, Qwen, Z-Image y taza original/recoloración. Los artifacts locales permanecen ignorados y no se copian a Git.

Los labels provienen de revisiones visuales documentadas del agente; **no son ground truth independiente humano**. El contrato real del reloj exigía dos agujas; no se sustituyó por la cantidad del ejemplo abstracto de la petición. El fallback técnico funcionó, pero su imagen con llave fusionada se etiqueta fail. La escena fría conserva expected uncertain: no se inventa un defecto confirmado.

Se hicieron **cero generaciones nuevas, vídeos, benchmarks GPU, descargas de pesos, instalaciones, cambios de workflow/encoder, reinicios o jobs Factory**. Las imágenes existentes bastaron para localizar limitaciones; generar más no aporta información ausente al extractor. Inferencia QA sobre artifacts existentes: Florence CPU cacheado y probes del judge local.

## Diagnóstico del coste anterior

Histórico de la fase anterior: QA gross91,875s y temporal101,422s. Son medidas de aquellos casos, no atribuciones al código nuevo. [Evidencia original](validation/flux-klein-4b-autonomous-2026-10-08.json).

Una instrumentación nueva del QA anterior sobre la imagen de tres agujas produjo69,169s, no100s constantes. [Registro](validation/visual-qa-latency-audit-2026-10-08.json):

| Etapa | Medida local |
|---|---:|
| Carga/reutilización Florence | 7,6192s |
| Caption incluyendo carga | 9,7834s |
| Caption después de cargar | 2,1642s, resta de etapas instrumentadas |
| HTTP LLM | 58,9640s |
| Wrapper, prompt/transport/extracción | 59,3853s |
| Judge incluyendo preparación/parseo | 59,3854s |
| Total | 69,1690s |

Servidor: prompt1808,128ms y generación de tokens56994,461ms, 1635 tokens de completion y533 de prompt. Respuesta:5642 caracteres de reasoning y543 de contenido final. No se guardó reasoning. El modelo/servidor domina el coste; la carga y caption CPU son secundarios. Preparación/parseo no se aislaron con precisión suficiente para atribuirles un coste independiente: diferencia wrapper/judge ≈0,0001s y wrapper/HTTP≈0,4213s incluyen varias operaciones. La metadata no permite separar exactamente tokens de reasoning y de respuesta final.

La ruta temporal anterior puede repetir caption de candidato, caption anterior y judge en llamadas secuenciales. La ruta gross/temporal no compartía resultados por contrato en estas comprobaciones. No se afirma una descomposición completa de las llamadas históricas92–101s porque sus timings internos no estaban disponibles.

[Probe sin thinking](validation/visual-qa-fast-judge-probe-2026-10-08.json), mismo caption: HTTP7,8554s, total8,2483s,191 tokens y0 caracteres de reasoning. Conservó verdict uncertain. Esa comparación demuestra ahorro en una llamada; no equivalencia de precisión sobre todo el dataset. Un judge compacto posterior respondió en22,7515s; ese tiempo se observó en consola, sin registro cronométrico versionado.

La comparación posterior de lógica antigua + transporte acotado obtuvo unavailable en cuatro casos (≈32s cada gross; ≈66s con dos judges temporales). Se detuvo exclusivamente el proceso evaluador propio. Una ablación sin response_format también falló: **no se ha demostrado incompatibilidad de grammar JSON**. La causa de latencia variable sigue sin resolver. [Intento parcial](validation/visual-qa-dataset-results-2026-10-08.json), [ablación](validation/visual-qa-format-ablation-2026-10-08.json). No aumentar timeout o reiniciar servidores para ocultarlo.

## Implementación y contrato

`app/services/visual_qa.py` implementa cuatro estados: pass, fail, uncertain, unavailable. Solo las restricciones explícitas activan sus checks. Ningún nombre de objeto o imagen tiene reglas especiales. El caller proporciona aliases de reconocimiento; el parser numérico y las máscaras son generales.

Ejemplo de contrato:

```json
{
  "subject": "container",
  "counts": [{"subject": "handle", "expected_count": 2, "tolerance": 0, "aliases": ["handles"]}],
  "geometry_constraints": ["silhouette", "part_arrangement"],
  "reference_image": "absolute/path/reference.png",
  "allowed_changes": ["lighting", "color", "texture", "rotation"],
  "temporal": {
    "expected_state": "surface visibly frosted",
    "required_evidence": ["frost"],
    "forbidden_evidence": [],
    "previous_state": "surface without frost",
    "previous_image": "absolute/path/previous.png"
  }
}
```

Jerarquía: sin restricciones, cero inferencias; caption una vez; OD solo para count; OCR solo si forbid_text; máscaras solo con geometry y referencia; estado solo si temporal. Un fail claro corta niveles posteriores. Evidencia/modelo ausente es unavailable; evidencia insuficiente es uncertain. El motor no realiza una cascada LLM obligatoria: un judge de texto no puede reconstruir las partes que el extractor no vio.

**Cantidad:** números explícitos y alcance del sustantivo; a/an exige acuerdo con detección. Disyunción, incertidumbre o conflicto de caption/reconocimiento se abstienen. Expected_count y tolerance son enteros no negativos, no booleanos. Grounding de una pieza no se usa como número de piezas. En los artifacts, OD reconoce el reloj pero no establece llave/aguja/fusión; captions pueden describir una pareja fusionada como un único objeto. Los tests de números no son validación perceptiva.

**Geometría:** segmentación por sujeto, soporte de polígonos agrupados nativos, máscara recortada y normalizada por escala/traslación, opcional orientación, Dice con tolerancia de borde. No compara píxeles RGB ni luz/color/textura. Bandas provisionales: ≥0,9 pass, <0,5 fail, intermedio uncertain; requieren calibración. La edición azul conserva silueta con score0,99259. Un contorno compatible no certifica distribución/número de partes ni identidad: pedir esas restricciones mantiene uncertain. No se ha separado automáticamente llave válida/deformada/fusionada con fiabilidad.

**Texto:** OCR detectó LONGINER y rechazó la inscripción inventada. La regla actual comprueba secuencias alfabéticas de tres o más caracteres; no certifica ausencia completa de texto, numerales o logos. Su recall no está validado. Es un detector parcial de violaciones, no una garantía de cumplimiento de todas las exclusiones del prompt.

**Temporal:** identity_score, state_score y progression_score son distintos. Identity_score queda null sin prueba fuerte, no se inventa1. Una pista presente establece estado; negación explícita puede refutarlo; omisión queda uncertain. Solo evidencia anterior observada incompatible con el nuevo estado establece progresión; narrar el estado anterior no basta. Cambios de iluminación no producen progresión por sí solos. El vocabulario de pistas todavía es literal y no interpreta sinónimos automáticamente; el caption puede decir smoke donde el contrato pidió steam. Eso produce abstención, no fail falso. Ambos captions pueden omitir evidencia relevante.

### Opt-in, admisión y compatibilidad

La integración permanece en el caller privado de MPT: requiere contratos explícitos `scene_qa_contracts` y booleano `openai_image_visual_qa_experimental_enabled=True`. No se añadió UI, planner automático, defaults ni configuración persistida. Los callers habituales mantienen QA anterior. Todos los modelos pueden evaluarse por el motor, sin regla que favorezca Klein.

Una evaluación conjunta evita duplicar gross/temporal solo cuando hay un contrato activo. El pipeline inyecta requisitos temporales ausentes y marca `identity_critical` para referencias factuales/continuidad. Ese requisito devuelve uncertain mientras no exista un método visual fuerte. Un contrato vacío conserva el gate anterior de Klein. Cualquier fail/uncertain/unavailable impide admitir la escena antes del root/render, sin retry ni fallback semántico. Los tres passes de la matriz son del motor directo, **no acreditan admisión del pipeline en continuidad crítica**.

`openai_image_qa_fast_local_judge=True` cambia exclusivamente los dos judges estructurados existentes: endpoint OpenAI-compatible loopback, thinkingfalse, temperatura0, máximo512 tokens, timeout30s,0 retries. El prompt pide JSON y el parser existente valida su estructura; no se garantiza respuesta por grammar. Solo message.content, jamás reasoning_content como sustituto; contenido vacío/truncado/error no pasa. No se cambió narración ni planificación.

### Caché y recursos

Caché de evidencia/verdict en memoria por tarea, LRU128, copias defensivas, sin imágenes/tensores nuevos persistidos. Clave: versiónQA, SHA256 candidato/referencia/imagen anterior, contrato completo, modelo+revisiónHF+dispositivo, tarea/query/crop/beam/tokenbound. Cambio de imagen, estado, requisito, modelo o versión invalida. Unavailable no se cachea. Florence se carga una vez por evaluación; solo el runtime existente conserva pesos y se libera al terminar el harness.

No descargas implícitas en el nuevo loader: local_files_only=True; el evaluador además fija HF_HUB_OFFLINE y TRANSFORMERS_OFFLINE. Beam1/tokens256 es una optimización experimental que puede alterar captions respecto a la ruta histórica; no se ha demostrado igualdad de recall. El modelo cacheado observado es florence-community/Florence-2-base-ft, revisión0b03b6f15a4a211370fb204aee4e7dd48887ea37.

`8080/props` declara vision=false/video=false/audio=false y un slot. No se encontró projector multimodal próximo al GGUF. OCR/grounding/segmentación Florence sí funcionan localmente; [probes](validation/visual-qa-florence-capabilities-2026-10-08.json), [crops](validation/visual-qa-focused-probe-2026-10-08.json). Segmentar fondo con rembg u operar máscaras con scipy no aporta conteo de partes internas; no se instalaron alternativas pesadas.

## Matriz de regresión

| Caso | Esperado | QA antiguo | QA nuevo | Tiempo antiguo | Tiempo nuevo |
|---|---|---|---|---:|---:|
| temporal_warm_512 | pass | unavailable (acotado) | uncertain | 66.395s | 9.779s |
| unrequested_text | fail | unavailable (acotado) | fail | 32.253s | 4.081s |
| valid_cloth_edit | pass | unavailable (acotado) | uncertain | 32.089s | 7.628s |
| identity_style_unframed_512 | pass | unavailable (acotado) | uncertain | 32.121s | 4.160s |
| identity_style_768 | pass | N/D | uncertain | N/D | 4.480s |
| style_identity_reversed_768 | pass | N/D | uncertain | N/D | 4.588s |
| continuity_factual_768 | fail | N/D | uncertain | N/D | 5.781s |
| mpt_t2i_text_contract_768 | fail | uncertain (histórico) | uncertain | 91.875s | 2.936s |
| mpt_temporal_hot_768 | pass | N/D | uncertain | N/D | 2.776s |
| mpt_temporal_cooled_768 | uncertain | uncertain (histórico) | uncertain | 101.422s | 2.700s |
| mpt_fallback_identity_style_seed43 | fail | N/D | uncertain | N/D | 4.314s |
| mpt_explicit_quantity_seed43 | fail | N/D | uncertain | N/D | 4.324s |
| z_image_t2i_768 | fail | N/D | uncertain | N/D | 2.882s |
| qwen_continuity_factual_768 | pass | N/D | uncertain | N/D | 4.225s |
| root_mug | pass | N/D | pass | N/D | 1.178s |
| valid_mug_recolor | pass | N/D | pass | N/D | 6.286s |

N/D significa no medido, nunca pass implícito. Las filas con “acotado” proceden del intento parcial de lógica anterior con transporte nuevo; no son los tiempos históricos unbounded. Las dos filas históricas provienen del checkpoint anterior; no son un replay pareado completo. Se muestran para trazabilidad, sin agregar métricas de regímenes distintos. La instrumentación fresh antigua69,169s sobre el reloj de tres agujas es una medición adicional.

**Métricas nuevas preliminares:** TP1 (defecto detectado), TN2 (válidos aceptados), FP0, FN0, uncertain13, unavailable0. Cobertura de decisión18,75%; se abstiene en5 de6 negativos y7 de9 positivos, más el expected uncertain. Los ceros FP/FN sobre tres decisiones **no prueban precisión global**. En operación fail-closed se bloquean también siete imágenes revisadas válidas; no se disfraza ese coste con la matriz binaria. No hay p95 con16 muestras.

Media4,5073s, mediana4,2692s, máximo9,7788s con primera carga. La repetición idéntica usa caché y tarda0.000845s en esta ejecución. No se presenta el ahorro frente a~100s como precisión equivalente: el motor rápido devuelve abstención mucho más a menudo. Los tiempos incluyen checks activados por cada contrato y caches compartidas dentro de este dataset, no warm/cold aislado para cada escena.

## Validación, seguridad y cierre

**387 tests +17 subtests aprobados,1 test integración omitido**, exit0,15,12s. Incluye241 casos históricos intactos,39 nuevos casos QA/control y107 casos LLM adicionales. [Log final](validation/visual-qa-final-tests-2026-10-08.txt). Tests offline: números/duplicado/ausencia/ambiguo; máscaras desplazadas/escaladas/deformadas y agrupación nativa; estado/negación/luz/progresión; unavailable, modelo ausente, timeout, respuesta inválida, caption vacío; caché de candidato/referencia/estado/modelo; cero inferencias sin requisito; cortocircuito; gates de contrato vacío/identidad/temporal; ningún retry ni red real en el bucle. No equivalen a detección real de agujas fusionadas. Warning existente Starlette/httpx; no se instaló nada.

Comando reproducible desde el worktree:

```powershell
$env:MPT_RUN_INTEGRATION_TESTS = '0'
$env:MPT_KLEIN_BRIDGE_BIN = Join-Path (Get-Location).Path 'local_image_stack\experiments\bridge\target\debug\klein4b-experimental-bridge.exe'
$qaTests = @(
  'test/test_klein4b_experiment.py', 'test/test_klein4b_graph.py', 'test/test_klein4b_rust_bridge.py',
  'test/services/test_klein4b_mpt.py', 'test/services/test_material_openai_image.py',
  'test/services/test_qwen_quality_v31.py', 'test/services/test_qwen_native_prompt_audit.py',
  'test/services/test_prompt_continuity_hardening.py', 'test/services/test_evidence_hardening.py',
  'test/services/test_evidence_pruning_root_qa.py', 'test/services/test_evidence_semantic_fallback.py',
  'test/services/test_corrective_continuity.py', 'test/services/test_visual_qa.py', 'test/services/test_llm.py'
)
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q @qaTests
$qaExit = $LASTEXITCODE
```

Comprobaciones: JSON, hashes de artifacts/referencias, diff/check y secretos sin imprimir coincidencias. [Cierre local](validation/visual-qa-final-access-checks-2026-10-08.json):8080health200,8090root404 (solo respuestaHTTP),8188stats200, cola0/0,8091 no iniciado, Factory/runs y lectura de logs accesibles. Stable conserva HEAD6d27ba4963ffe469d635db71eaeec506a8ff4b61, sin cambios tracked; backups untracked preexistentes se conservaron. No se afirma stable status limpio.

Klein, Qwen y Z-Image conservan sus modelos/workflows y condiciones. La matriz incluye sus imágenes pero no es ranking de calidad ni benchmark de generación. Qwen válido queda uncertain cuando el QA no establece estructura; no es un nuevo defecto del generador.

**Siguiente tarea concreta:** seleccionar/evaluar un extractor o judge visual local capaz de contar partes y comparar estructura/estado sobre este mismo dataset, con ejemplos positivos/negativos y adjudicación humana independiente. Primero comprobar un candidato disponible y su compatibilidad/VRAM; si necesita pesos/modelo/dependencia pesada o habilitar un servidor multimodal, requiere una decisión separada. No descargar ni reconfigurar aquí. Resolver además latencia variable del judge acotado con telemetría por solicitud. Hasta entonces conservar defaults, fail-closed y routing desactivado; no resolver el bloqueo repitiendo generaciones.

Resultados intermedios se conservan identificados: v1 tenía parser de polígonos insuficiente; v2 lo corrige; [resultado final](validation/visual-qa-final-results-2026-10-08.json) es la referencia de esta implementación. [Handoff operativo](VISUAL_QA_HANDOFF.md).
