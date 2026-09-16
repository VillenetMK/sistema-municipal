# Validación de la versión 0.1

Fecha: 16 de septiembre de 2026.

## Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Pruebas Python | 31 aprobadas |
| Análisis estático Ruff | Sin errores |
| Construcción de las pantallas | Login, resumen, bandeja, registro, detalle y catálogo; anchos 390 y 1280 |
| Arranque del servidor Flet | HTTP 200 y documento de inicio del cliente servido |
| Esquema SQL en PostgreSQL aislado (PGlite) | Ambas migraciones aplicadas correctamente |
| Contrato SQL | Roles, aislamiento por área, idempotencia, control de versión, estados, bloqueo de edición directa, adjuntos y auditoría aprobados |
| Migraciones en Supabase municipal | `20260916153745_municipal_core` y `20260916154951_municipal_access_hardening` |
| Consultas anónimas a la API real | `cases` y `staff_profiles` rechazadas con HTTP 401 |
| Asesor de seguridad de Supabase | Sin avisos al finalizar los cambios |
| Asesor de rendimiento | 13 índices todavía sin uso; información esperable en tablas nuevas sin datos operativos |

Los índices soportan filtros, relaciones y ordenaciones del flujo; no se eliminaron por falta de uso en una base nueva. [Explicación del aviso](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).

El proyecto municipal tiene ocho tablas públicas protegidas por RLS, un contador interno en `private` y un bucket documental privado. Los únicos datos iniciales son la configuración institucional pendiente, tres áreas de referencia y la solicitud general. No se crearon cuentas Auth, personas ni expedientes reales. No se modificó EcoSphere.

## Límites de esta validación

La comprobación de pantallas construye controles con la versión instalada de Flet; no equivale a una revisión visual de píxeles. El navegador de revisión no pudo abrir la dirección local de este entorno. Se verificaron por separado el arranque HTTP y la construcción de los controles.

Las políticas se probaron en un PostgreSQL aislado con esquemas Auth y Storage mínimos; la API real se comprobó como cliente anónimo. Faltan pruebas integrales con usuarios municipales reales, cargas y descargas desde dispositivos reales, accesibilidad con lectores de pantalla, concurrencia bajo carga y restauración de respaldos.

No se compilaron APK, instaladores Windows/Linux ni paquetes iOS/macOS. No se publicó la aplicación web. Las capacidades de despliegue y empaquetado están documentadas, no certificadas para todos los destinos.

El historial de pruebas SQL se ejecuta dentro de una transacción con rollback. Los scripts de bootstrap son únicamente para bases locales de pruebas. El workflow del repositorio repetirá las comprobaciones en PostgreSQL 17.
