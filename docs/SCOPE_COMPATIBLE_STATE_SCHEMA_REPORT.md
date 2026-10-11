# Schema de estado compatible con el scope — 2026-10-11

Desde `56db28af2f941acb2888af2ea3f35d77d009a8f6`, se añade un constructor experimental que limita el enum de estado a los valores aceptados para el scope declarado. La fase es exclusivamente CPU: **cero consultas nuevas a modelos**. El usuario pide cerrar la sesión; se guarda y publica este checkpoint y se detiene el trabajo hasta su reanudación. La modernización completa sigue pendiente.

## Cambio acotado

[`scripts/scoped_state_schema.py`](../scripts/scoped_state_schema.py), versión `scope-compatible-state-schema-1`, reutiliza el constructor publicado de payload y valida el scope antes de emitir el schema. Solo sustituye `allowed_state_change.enum`:

| Estados permitidos declarados | Enum emitido |
|---|---|
| Lista vacía | `not_applicable` |
| Lista no vacía | `observed`, `not_observed`, `uncertain` |

Cuando hay vapor permitido declarado y no se observa vapor, el contrato exige `not_observed`, no `not_applicable`. No se convierte ninguna respuesta antigua a ese valor. Prompt, imágenes, roles, controles de metadata, nombre del schema, 512 tokens, temperatura y thinking permanecen iguales en la comparación de payloads.

El módulo es un **constructor**, todavía sin conexión automática al collector anterior ni a la app. El observador publicado, su schema genérico, parsing y validador quedan intactos. El nuevo schema limita únicamente la aplicabilidad del estado: las relaciones entre presencia, estructura y conexiones siguen necesitando el validador estricto de runtime. No acredita identidad ni autoriza admisión o rechazo automático.

## Pruebas y replay verificables

[`test/test_scoped_state_schema.py`](../test/test_scoped_state_schema.py): 21 regresiones nuevas sobre scopes vacíos/no vacíos, valores inválidos, contaminación entre schemas, metadata, equivalencia del payload salvo el enum, respuestas archivadas y conservación de reglas relacionales/diagnóstico.

- [RED anterior a implementar](validation/scoped-state-schema-red-tests-2026-10-11.txt): 21 fallos, 0,49 s, exit 1, por módulo/API ausente.
- [Validación final de esta fase](validation/scoped-state-schema-final-tests-2026-10-11.txt): **168 pasan, 2,19 s, exit 0**; 21 nuevas y 147 anteriores, con integración desactivada, Python MPT y sin acceso a modelos.
- Revisión independiente enfocada: sin hallazgos accionables; ejecución independiente de las 21 nuevas, 0,26 s/exit 0. No sustituye la evidencia del run final guardado.

Comando del run final desde el worktree, con `MPT_RUN_INTEGRATION_TESTS=0`, `HF_HUB_OFFLINE=1` y `TRANSFORMERS_OFFLINE=1`:

```powershell
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test/test_scoped_state_schema.py test/test_scoped_structure_observations.py test/test_paired_shape_observations.py test/test_paired_shape_preflight.py test/test_paired_shape_runner.py test/test_prepare_visual_regions.py --tb=short
```

[Receta CPU](validation/scoped-state-schema-replay-recipe-2026-10-11.py), [resultado](validation/scoped-state-schema-replay-2026-10-11.json): 40 combinaciones de aplicabilidad, dos respuestas reales archivadas y tres payloads procedurales comparados. Schema nuevo y runtime coinciden en esa matriz, con los otros campos coherentes; no se afirma equivalencia para todas las restricciones relacionales. Los pins anteriores de ejecución/preparación siguen verificándose.

Las dos respuestas antiguas conservan bytes, valor `not_applicable` y rechazo por scope. El schema genérico anterior las acepta; el nuevo schema y el runtime anterior las rechazan. No se crea una nueva observación ni se relabelan cohortes cerradas. Los tres requests futuros difieren solo en el enum y tienen SHA distintos de los anteriores; ninguno se ejecuta. El historial continúa teniendo únicamente dos consultas de esa cohorte fallida, y los pares de vapor/unión rota siguen sin consultarse.

## Cierre y próxima sesión

[Comprobaciones de cierre](validation/scoped-state-schema-closing-checks-2026-10-11.json): bindings, logs, sintaxis/JSON, diff, ausencia de patrones de secretos y protección de estable. SHA de entrega mediante Git/origin después del commit; base del checkpoint arriba. Sin generación, descarga, benchmarks, jobs, procesos de modelo ni cambios de servicios compartidos en esta fase.

Próxima tarea concreta: preparar una cohorte distinta que use explícitamente `scoped_state_schema.payload`, registre el **SHA del request realmente enviado** y conserve el validador estricto y raw HTTP. No reutilizar el collector genérico bajo metadatos del schema nuevo ni modificar el resultado previo. Fijar plan, inputs, pesos/runtime existentes, presupuesto y comprobaciones de recursos antes de cualquier inferencia; cerrar únicamente procesos propios. Ningún juez geométrico está aprobado: calibración independiente, errores/abstención y QA completo siguen pendientes. No hace falta revisión humana adicional ni abrir servidores para cerrar este checkpoint.
