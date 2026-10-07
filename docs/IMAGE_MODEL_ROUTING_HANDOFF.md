# Handoff de auditoría de modelos — 2026-10-07

## Procedencia y alcance

Documentos reconstruidos en Windows por autorización explícita del usuario. El agente remoto, según informa el usuario, los había creado en `ab8e483` local y no los publicó. No se recuperó ese objeto ni se presentó su investigación como completada. La auditoría de esta sesión parte del código e historial realmente disponibles.

Worktree: `D:\Apps\MPT-worktrees\image-model-routing-modernization`. Rama: `factory/image-model-routing-modernization`. Base de código: `7b2c303196fe16f9844a9ba3f081e8f296bc1dd9`. Preparación publicada: `e759b39072bb32959ad06d86106c21f7da3b117a`. El commit documental que contiene este archivo es el checkpoint de cierre, identificable con `git log -1 --format=%H -- docs/IMAGE_MODEL_ROUTING_HANDOFF.md`; no confundirlo con la base.

## Trabajo realizado

- HEAD/status/diff/handoffs comprobados. Fetch de origin: sin divergencia; se conservó el checkpoint de preparación.
- Revisión por patrones de secretos en `AGENTS.md` y el handoff local antes de publicar. El primer push falló por credenciales; el usuario autorizó Git Credential Manager y completó login en navegador. El siguiente fetch/push publicó `e759b39` sin force-push. No se guardaron credenciales en el proyecto.
- Se documentaron las fases de código ya existentes: fixes de outputs/estado temporal, Precision sin referencias y deduplicación, con sus commits y tests. No se reimplementaron ni se lanzaron sus pruebas históricas.
- Se contrastaron configuración local seleccionada, funciones de routing/payload/perfil y fuente del bridge, workflows en disco, nodos/asset lists vivos y capacidad GPU. No se cargó ningún modelo por estas comprobaciones.
- Se consultaron fuentes oficiales actuales para baseline y selección de candidatos. Fuentes, hechos publicados, observaciones y estimaciones separados en [RND](IMAGE_MODEL_ROUTING_RND.md).

## Hallazgos que condicionan la continuación

1. Standard Z Turbo, Precision Qwen 2.1 y fallback Klein son aliases concretos, no garantías de capacidad intercambiable. Las promociones de continuidad y fallback alteran la ruta efectiva.
2. Balanced Qwen usa `768x1376`, 20 pasos y un candidato por precedencia de perfil; el template aislado y los ajustes genéricos no describen toda ejecución.
3. `flux-klein-precision` referencia Klein **9B KV** y no tiene disponibles en los loaders vivos `qwen_3_8b_fp8mixed.safetensors` ni `flux2-vae.safetensors`. No se reparó; la plantilla cargada por el proceso bridge sigue sin verificar.
4. Qwen 2.1 tiene licencia de investigación; Klein 9B tiene licencia no comercial del modelo. Klein 4B, Z Turbo/Base y Qwen Edit 2511 declaran Apache 2.0 para sus modelos. Revisar cada componente concreto antes de adopción. Las condiciones de outputs y las del uso del modelo son distintas.
5. Klein 4B destilado es el primer candidato documental propuesto; no está adoptado ni validado en esta 3060. Las cifras oficiales de memoria de BFL varían según fuente y no permiten garantizar el pico local.
6. La igualdad del workflow Qwen local con el externo se comprobó como JSON, no por bytes. Todos los nodos de los tres workflows están registrados; ese dato no prueba que los tres puedan ejecutar con los assets disponibles.

## Verificación y límites

Evidencia local y comprobaciones documentales: [registro JSON](validation/image-model-routing-audit-2026-10-07.json). Revisión final de scope, secretos por patrones, referencias locales, commits citados y `git diff --check`. No se ejecutaron tests de aplicación porque solo se modifica documentación; no hay nueva certificación funcional.

Sin cambios de producción, modelos, dependencias, workflows o servicios; sin descargas de pesos, generación, benchmarks, force-push, merge ni publicación de vídeos. La copia estable y las demás ramas no se modificaron. La ocupación GPU leída es un snapshot global, no un perfil de inferencia.

## Siguiente tarea

Preparar únicamente el plan de integración aislada de Klein 4B destilado: variantes/aliases, manifiesto de pesos y licencias, diferencias respecto a Klein 9B KV, payloads T2I/edit/continuidad, condiciones de fallback, tests offline y criterios de aceptación. Incorporar el diagnóstico del fallback actual y aclarar el destino comercial o de investigación antes de recomendar un despliegue. Toda instalación, edición de producción/workflows, descarga o prueba GPU necesita un nuevo encargo específico.

Si se aporta `ab8e483`, reconciliar sus conclusiones sin reemplazar automáticamente este historial. Para continuar, confirmar branch/HEAD/status y volver a hacer fetch; conservar cualquier nuevo cambio válido.
