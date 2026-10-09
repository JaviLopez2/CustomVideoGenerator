# Replay de observaciones pareadas retenidas — 2026-10-09

Base `6e28a56561b607f0876582664f8fe35207719ec1`, worktree y rama `factory/image-model-routing-modernization`. Se conservaron los archivos nuevos de la implementación en curso; no había cambios tracked o staged al retomar. Diez worktrees comprobados. Tras fetch, divergencia local/origin `0/0`. SHA de cierre mediante Git/origin; el SHA base no identifica esta entrega.

Se completa el adaptador experimental `scripts/retained_paired_observations.py`. Reproduce cuatro informes existentes con sus contextos originales, sin cargar pesos, consultar modelos, generar imágenes o modificar la aplicación. [Diseño previo conservado](validation/retained-paired-replay-design-2026-10-09.json), [ejecución fijada antes del replay](validation/retained-paired-replay-execution-plan-2026-10-09.json).

## Correspondencia y autoridad

El loader verifica JSON acotado sin claves duplicadas, SHA de raw/plan/código, modelo declarado contra el manifiesto de assets, fuentes y preparación nativa, roles, sujeto, consulta y fingerprint del payload original. Reconstruye recortes/fotogramas con los helpers existentes. El snapshot distingue fuente original de imagen preparada: retirar metadata puede cambiar el SHA sin cambiar píxeles. Las rutas de imágenes son absolutas y pertenecen a la raíz; las rutas de filas raw no se siguen.

La consulta exige el par ordenado y su contexto; un candidato solo no identifica la observación. Revalida fuentes/preparación antes de consultar, mientras las mutaciones del archivo raw/plan no reescriben el snapshot. Un caso no registrado devuelve `unavailable`, sin inventar una respuesta. Una fila inválida mantiene su contenido final y fallo; no se rescata por reason, summaries o labels.

Salida válida: `uncertain`, disponibilidad limitada a salida registrada; identity/state/progression scores `null`. Admisión, rechazo automático, identidad física, temperatura y verdad perceptual permanecen false. La cobertura rectangular reconstruida no acredita cobertura semántica. No se importa el adaptador desde `app`, se sustituye `scoped_qa`, o se modifica selección/reintentos/caché/gates/defaults.

## Resultado CPU real

[Exportación](validation/retained-paired-replay-result-2026-10-09.json), [log CLI](validation/retained-paired-replay-execution-2026-10-09.txt): exit0, 5,964s de replay CPU. Este tiempo no es inferencia de juez ni latencia de QA completo. [Verificador](validation/retained-paired-replay-verifier-2026-10-09.py), [prueba](validation/retained-paired-replay-verification-2026-10-09.json), [log](validation/retained-paired-replay-verification-execution-2026-10-09.txt): exit0.

| Cohorte retenida | Contextos previstos | Filas raw existentes | Salida del replay |
|---|---:|---:|---|
| Cue Qwen3.5-9B | 4 | 4 | 4 uncertain |
| Cue Qwen3-VL-8B | 4 | 1 | 1 raw inválido unavailable; 3 no ejecutados unavailable |
| Forma Qwen3.5-9B | 3 | 3 | 3 uncertain |
| Forma Qwen3-VL-8B | 3 | 3 | 3 uncertain |

Son **14 contextos, 11 filas retenidas, 10 uncertain y 4 unavailable**, con cero nuevas consultas. Los once contenidos finales/status/finish/reasoning coinciden literalmente con el raw. El sujeto equivocado, consulta equivocada y par inverso no registrado devuelven unavailable en los controles aplicables. Los 22 bindings de fuentes fijados permanecen intactos. Se conserva el riesgo semántico del último cue Qwen3.5; no se corrige ni se convierte en etiqueta humana. No se mide precisión ni se escoge candidato.

## Pruebas y revisión

**282 tests relevantes pasan en15,87s, exit0/sin avisos**, 100 del nuevo adaptador y182 de sus runners/parsers/preflight/preparación. [Log final](validation/retained-paired-replay-final-tests-2026-10-09.txt). Modelos/red/runtime simulados y prohibidos en las pruebas del loader; integración desactivada. Fuentes sin cambio después de esa ejecución.

El historial RED/GREEN se conserva: stubs fallaron; el archivo denominado `green-tests` contiene realmente81pass/1fail por un fixture donde el par invertido coincidía con otro par legítimo. Se corrigió ese fixture, no el comportamiento, y se añadió un control explícito de inverso registrado. Los logs posteriores previos al cierre92/274 son históricos respecto de la corrección siguiente; no sumarlos como tests adicionales.

La revisión detectó P2: los checks resolvían rutas relativas contra `root`, mientras la reconstrucción/payload leían contra CWD. Reproducción con fuente interna corrupta y homónimo externo válido: seis regresiones source/crop/case fallaron en ambos protocolos; dos controles absolutos pasaron. [RED real](validation/retained-paired-replay-cwd-red-tests-2026-10-09.txt). Corrección: rechazar descriptores relativos antes de delegar, preservando helpers originales e informes. [GREEN](validation/retained-paired-replay-cwd-green-tests-2026-10-09.txt):8pass/92deselected/1,39s/exit0. Revisión posterior: no issues, P2 resuelto.

[Cierre de archivos y Git](validation/retained-paired-replay-closing-checks-2026-10-09.json). No modelos, dependencias, workflows, servicios, labels, producción o routing modificados. Los logs crudos de fallos se conservan sin corregir sus espacios de pytest.

## Próxima tarea y objetivo completo

Siguiente: puente diagnóstico explícitamente inyectado en el punto privado existente de MPT, con tests de no interferencia y declaración del par/etapa de imagen. Mantener el store monoimagen, QA y defaults; no importar scripts experimentales desde producción ni usar diagnósticos como autorización. Preparación CPU autónoma, sin8080 ni intervención rutinaria.

Siguen pendientes negativos estructurales válidos de otra familia, calibración de cantidad/geometría/estado con revisión independiente, cobertura semántica, errores/abstención, latencia completa y elección del juez. A/B/C humano y labels/captions históricos intactos. El éxito del replay verifica trazabilidad de datos y contexto, no esas capacidades. Objetivo global activo y sin completar.
