# Operación local de MPT en Windows

## Rutas y contexto

- Repositorio de trabajo: `D:\Apps\MPT-worktrees\image-model-routing-modernization`.
- Rama experimental actual: `factory/image-model-routing-modernization`. Confirmar siempre carpeta, rama, HEAD, status y `git worktree list`; no asumir que este estado sigue vigente.
- Factory: `D:\Apps\MPT-Agent-Factory`; logs y artifacts: `data\runs` dentro de Factory.
- Configuración Factory de este experimento: `D:\Apps\MPT-Agent-Factory\factory-image-model-routing-modernization.toml`. Leerla sin imprimir secretos; no iniciar supervisor ni encolar jobs por defecto.
- Python configurado para MPT: `D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe`.
- Python de Factory: `D:\Apps\MPT-Agent-Factory\.venv\Scripts\python.exe`.
- ComfyUI: `C:\Users\JAVIER\ComfyUI-Installs\ComfyUI\ComfyUI`.
- Bridge: `D:\Comfyui2Openai\apps\api`.
- MPT estable protegido: `D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\MoneyPrinterTurbo`, rama `moneyprinter_qwen21_quality_v3_1`. No modificar sus archivos ni avanzar su rama. No escribir ni promover cambios a `main` sin autorización específica.
- Los worktrees comparten los metadatos Git en `.git` del repositorio estable. Las operaciones Git del experimento pueden necesitar escalación específica; esto no autoriza modificar el árbol estable ni sus refs protegidas.

Leer `AGENT_FACTORY_STATE.md`, `docs/EVIDENCE_CONTINUITY_HANDOFF.md`, `docs/LOCAL_WINDOWS_ACCESS_HANDOFF.md` y `D:\Apps\MPT-Agent-Factory\WORK_HANDOFF.md`. Las rutas y pruebas Linux de handoffs históricos no acreditan el estado de Windows. Leer también los `AGENTS.md` aplicables antes de trabajar en otra carpeta; conservar instrucciones válidas.

## Reglas de trabajo

- Autorización vigente del usuario, 2026-10-09: avanzar de forma continuada y autónoma según el plan experimental, ejecutando pruebas y mejoras rutinarias sin pedir otro «sigue» después de cada checkpoint. Mantener el objetivo persistente del chat y registrar decisiones, presupuestos y resultados. Un checkpoint no es una pausa ni una petición de permiso. Las valoraciones humanas que falten se registran como pendientes, sin inventarlas; avanzar en tareas independientes cuando sea posible. Esta continuidad conserva la protección de producción y los permisos efectivos de la sesión. Estado y próxima acción en `docs/AUTONOMOUS_MPT_WORK_HANDOFF.md`.
- Ejecutar los comandos y leer sus resultados directamente; no delegar al usuario la copia de comandos o salidas.
- Trabajar en ramas/worktrees experimentales. Reutilizar el actual si es adecuado; usar `codex/` para nuevas ramas salvo indicación distinta del usuario.
- Revisar status y diff, incluidos cambios staged, antes de editar. Conservar cambios existentes; no hacer resets, limpiezas ni staging indiscriminado.
- Resolver decisiones rutinarias dentro de la tarea autorizada. Detenerse ante bloqueos reales o ampliaciones de alcance.
- No modificar MPT estable, hacer force-push, auto-merge ni publicar vídeos.
- No cambiar dependencias globales, descargar modelos ni ejecutar benchmarks GPU sin autorización específica. No iniciar, detener o reiniciar servicios si la tarea no lo requiere y autoriza.
- No mostrar ni guardar claves, tokens o secretos en documentos, logs de validación o commits. Evitar volcar configuraciones completas y argumentos de procesos.
- Validar cambios con tests relevantes, ampliar cuando proceda y revisar el diff final. Guardar checkpoints locales en la rama experimental y un handoff con HEAD, archivos, pruebas reales, logs y pendientes. Añadir solo los archivos de la tarea; no incluir configuraciones privadas ni artifacts de generación.
- Respetar los permisos efectivos de la sesión. Si falla el sandbox, usar el mecanismo de escalación disponible con alcance explícito; no eludir revisiones ni atribuirse permisos permanentes.

## Tests y servicios

Desde el worktree experimental, en PowerShell:

```powershell
$env:MPT_RUN_INTEGRATION_TESTS = '0'
& 'D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe' -B -m pytest -q test
```

Para tests enfocados, sustituir `test` por los archivos o casos afectados. Registrar el exit code de Python y la salida en un log local, sin secrets, y referenciarlo en el handoff. No atribuir resultados históricos a un nuevo cambio. La presencia de pytest no garantiza que todas las dependencias estén disponibles; diagnosticar fallos sin instalar nada globalmente.

Para una tarea autorizada sobre Factory, ejecutar desde `D:\Apps\MPT-Agent-Factory`:

```powershell
& 'D:\Apps\MPT-Agent-Factory\.venv\Scripts\python.exe' -B -m pytest -q tests
```

Health checks de solo lectura, timeout de 3 segundos: `http://127.0.0.1:8080/health`, `http://127.0.0.1:8090/`, `http://127.0.0.1:8188/system_stats`. Un 404 del bridge confirma respuesta HTTP, no readiness de generación. No enviar solicitudes de generación para comprobar disponibilidad.
