# Constancias y reportes

## Constancia de un expediente

Abrir **Expedientes**, entrar en una solicitud y pulsar **Constancia PDF**. El archivo incluye el código, la fecha de registro en Chiclayo, el solicitante, el documento de identidad parcial, el canal, el asunto y la descripción completa. También identifica el estado, área, trámite, cantidad de adjuntos y versión que tenía el expediente al emitir esa copia.

La fecha de registro y la fecha de emisión tienen etiquetas distintas. Una copia posterior puede reflejar otro estado o área. La constancia no incorpora firma digital ni sustituye la constancia del SGD municipal, una resolución o la aprobación del trámite. Los PDF de demostración llevan **DEMOSTRACIÓN - DATOS FICTICIOS** en cada página.

## Reporte de todos los resultados

1. En **Expedientes**, elegir los criterios y pulsar **Aplicar filtros**.
2. Abrir **Reportes**. La pantalla muestra el alcance de la cuenta, los filtros, la hora del corte y los indicadores.
3. Pulsar **CSV completo** para obtener una fila por resultado, o **Resumen PDF** para los indicadores y las distribuciones por estado, prioridad y área.

Los campos modificados pero aún no aplicados no se incorporan al reporte. **Actualizar reporte** y cada descarga vuelven a consultar la base: el corte y los totales pueden cambiar si hubo nuevas actuaciones. El CSV de página sigue disponible como una descarga separada y limitada a lo visible.

El CSV completo incluye código, asunto, estado, área actual, trámite vinculado, responsable, prioridad, canal, ingreso en Chiclayo, objetivo interno, versión y fecha de corte. Se abre en Excel como un archivo CSV UTF-8. Omite solicitantes, documentos de identidad y contactos; el asunto conserva el texto escrito al registrar. Las celdas que podrían interpretarse como fórmulas reciben protección. Es CSV, no un libro XLSX.

El reporte admite hasta **10000 expedientes** por consulta. Si el resultado supera esa cantidad, se rechaza la exportación y se pide reducir el período o añadir filtros. Nunca se entrega una lista truncada como si fuera completa. Se pueden generar reportes sin resultados.

## Cómo interpretar los indicadores

| Indicador | Cálculo sobre los resultados filtrados |
|---|---|
| Resultados | Todos los expedientes incluidos en el corte |
| Pendientes | Estados Recibido, En revisión y Observado |
| Objetivo interno vencido | Pendientes con fecha objetivo anterior al día del corte en Chiclayo |
| Pendientes sin responsable | Pendientes que aún no tienen responsable asignado |
| Distribuciones | Cantidades de todos los resultados por estado, prioridad y área actual |

Las fechas objetivo siguen siendo internas. El reporte no calcula vencimientos legales ni equipara archivado con atención efectiva.

## Permisos y consistencia

Cada descarga vuelve a comprobar la sesión y el perfil. Administrador y mesa de partes tienen el alcance general; gestor y consulta conservan el alcance de su área. Un filtro no concede acceso adicional. No hay enlaces públicos de consulta ni de descarga.

Las funciones `export_case_report` y `case_receipt` usan `SECURITY INVOKER` y las políticas RLS existentes. El reporte se entrega en una sola respuesta JSON, sin depender del límite REST de 1000 filas ni combinar páginas de distintos momentos. Las funciones `STABLE` usan la [instantánea de la consulta de PostgreSQL](https://www.postgresql.org/docs/17/xfunc-volatility.html); la autorización conserva la [RLS de Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security).

Los archivos se generan en memoria con Python. Las descargas no crean expedientes, adjuntos ni eventos de actuación. Los PDF usan ReportLab y fuentes incluidas en el paquete; no necesitan una instalación de Office. Los caracteres no disponibles en la fuente se representan con `?`; el CSV conserva el texto Unicode original.

## Actualizar el equipo

Cerrar MuniGest y ejecutar en la carpeta del repositorio, desde la terminal de VS Code:

```powershell
git pull --ff-only origin main
py -3.12 -m uv sync --frozen --extra desktop
.\.venv\Scripts\python.exe run.py
```

Esta entrega añade una dependencia para generar PDF; por eso es necesario ejecutar también la sincronización de paquetes. La migración municipal ya está aplicada en `lxvmwjcqdjoidgpinmgm`. No se requiere volver a crear la base.
