# Preparación de acceso local — 2026-10-07

Alcance: preparar operación autónoma en este Windows. Modernización detenida; sin tests, benchmarks, generación, cambios de dependencias ni cambios de servicios.

## Estado comprobado antes de añadir documentación

- Carpeta: `D:\Apps\MPT-worktrees\image-model-routing-modernization`.
- Rama: `factory/image-model-routing-modernization`.
- HEAD de partida: `7b2c303196fe16f9844a9ba3f081e8f296bc1dd9`.
- Status y diff staged/unstaged vacíos. `git worktree list` confirma diez worktrees, incluida la copia estable.
- Se añadió únicamente `AGENTS.md` y este handoff, conservando los documentos existentes. El checkpoint documental posterior se identifica en el historial Git; el HEAD anterior no es su SHA.

## Accesos comprobados

- Lectura de Factory, `data\runs` (20 entradas), un `worker.log`, ComfyUI y bridge mediante ejecución fuera del sandbox aprobada por el mecanismo de revisión de la sesión.
- Python MPT configurado por Factory: `D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\lib\python\python.exe`, versión 3.11.15; pytest disponible. Probe con `-I -B`, sin importar MPT ni ejecutar tests.
- La configuración experimental Factory apunta a este worktree y a esta rama. No se modificó.
- GET local con timeout de 3 segundos: 8080 `/health` = 200; 8090 `/` = 404; 8188 `/system_stats` = 200. No certifican calidad ni generación.
- No había `AGENTS.md` en el worktree ni en los directorios superiores comprobados. Se leyó el existente de ComfyUI y los handoffs de MPT/Factory.

## Permisos y limitaciones

- La sesión declara el worktree experimental como escribible y usa `approvals_reviewer=auto_review`. Las escalaciones de lectura se ejecutaron correctamente; esto no concede permisos permanentes a futuras operaciones.
- El ejecutor restringido falla antes de iniciar PowerShell: `helper_unknown_error: setup refresh had errors`.
- La configuración local de Codex ya indica `[windows] sandbox = "elevated"`; no se cambió la configuración global ni las ACL.
- El log documentado `C:\Users\JAVIER\.codex\.sandbox\sandbox.log` contiene un error del 2026-04-16: `helper_firewall_rule_create_or_add_failed`, `SetRemotePorts`, HRESULT `0x80070057`. Es un antecedente, no prueba de la causa del fallo actual.
- No hay una herramienta de esta sesión para modificar el selector de permisos o rehacer la instalación del sandbox. No se requiere acceso completo para los accesos ya comprobados mediante escalación.
- Si se necesita reparar el sandbox ordinario: reiniciar Codex y reintentar la configuración de Agent sandbox cuando la interfaz la ofrezca; el usuario debe aceptar el diálogo UAC si aparece. Referencia: https://learn.chatgpt.com/docs/windows/windows-sandbox.
- Mantener el selector de permisos en `Approve for me` / `Aprobar por mí` para revisión automática de escalaciones elegibles; ya está activo en esta sesión. Referencia: https://learn.chatgpt.com/docs/sandboxing.
- Metadatos Git compartidos: `D:\Apps\MoneyPrinterTurbo-Portable-Windows-1.3.6\MoneyPrinterTurbo\.git`, fuera de la raíz escribible. Solicitar escalación específica para checkpoints experimentales si procede; mantener protegidos el árbol estable y sus ramas.

## Continuación

Esperar una nueva tarea. Ejecutar comandos, editar y validar dentro de su alcance, conservar cambios existentes, guardar logs y checkpoints con handoff. No retomar la modernización por iniciativa propia. Las reglas y comandos de tests están en `AGENTS.md`.
