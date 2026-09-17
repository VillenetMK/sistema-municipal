# Expedientes y bandeja de trabajo

## Registrar una solicitud

Mesa de Partes y Administrador pueden abrir **Registrar solicitud**. El formulario recoge solicitante, asunto, descripción, trámite, área, canal, prioridad y fecha objetivo interna opcional.

El trámite inicial es **Solicitud general** cuando está activo. Elegir otra ficha propone su área de destino si la tiene; el operador puede ajustar el área según el caso. Los requisitos y el sustento de la versión elegida quedan conservados en el expediente, aunque el catálogo cambie después. No se aplican tarifas ni plazos legales automáticamente.

**Responsable (opcional)** muestra personas activas del área elegida con rol Administrador, Mesa de Partes o Gestor. Puede dejarse **Pendiente de asignación**. Cambiar de área limpia la selección de responsable para evitar asignarlo a alguien que no podrá atenderlo.

Los clientes anteriores que omitan el trámite reciben la ficha GENERAL activa. Si esta ya no está activa, deben actualizarse y seleccionar una ficha vigente. Los expedientes anteriores a esta migración no se reclasifican automáticamente; pueden vincularse desde Organización mientras sigan abiertos.

## Organizar el expediente

Dentro del detalle, **Organización del expediente** muestra la ficha conservada, responsable, prioridad y fecha objetivo. Quienes tienen permiso de atención pueden cambiar esos datos y registrar el **Motivo de la organización**. **Guardar organización** conserva el antes y el después en el historial.

Administrador y Mesa de Partes pueden organizar los expedientes de todas las áreas. Gestor puede organizar los de su área. Consulta no modifica datos. La asignación no concede acceso a expedientes de otras áreas y no impide que otro gestor autorizado de la misma área intervenga.

Una ficha desactivada puede mantenerse en un expediente existente; no se admite como nueva clasificación. Guardar cambios de responsable o fecha no reemplaza su copia histórica. Vincular un trámite diferente guarda la ficha vigente de ese nuevo trámite. Para conservar trazabilidad, no hay actualización automática de fichas antiguas.

Los expedientes atendidos o archivados no permiten editar su organización. El paso de Atendido a Archivado continúa en **Registrar actuación**. Una versión obsoleta del expediente rechaza el guardado: volver a la bandeja y abrirlo otra vez permite revisar lo que cambió.

## Derivar a otra área

Usar **Registrar actuación**, seleccionar el área de destino y explicar el motivo. La derivación conserva el trámite y libera al responsable anterior. El expediente aparece **Sin responsable** para que el área receptora lo asigne. Los gestores del área anterior dejan de verlo según la política de acceso por área.

Antes de desactivar a una persona, moverla de área o convertir su rol en Consulta, sus expedientes pendientes deben reasignarse o quedar sin responsable. Los atendidos y archivados conservan su relación histórica.

## Usar la bandeja

| Acceso o filtro | Resultado |
|---|---|
| Mis pendientes | Asignados a la cuenta actual y todavía sin atender ni archivar |
| Sin responsable | Pendientes sin una persona asignada |
| Objetivo hoy | Pendientes cuya fecha objetivo interna es hoy en Chiclayo |
| Estado, área, trámite, responsable y prioridad | Restringen los resultados por los valores elegidos |
| Ingreso desde / hasta | Incluyen los días completos en horario de Chiclayo, con formato AAAA-MM-DD |
| Objetivo vencido | Pendientes con objetivo anterior a hoy |
| Objetivo en próximos 3 días | Pendientes con objetivo entre mañana y los tres días siguientes a hoy |
| Sin fecha objetivo | Expedientes cuya fecha objetivo no está registrada |
| Limpiar filtros | Restablece la búsqueda y muestra todos los expedientes autorizados |

Después de cambiar campos, pulsar **Aplicar filtros**. Los accesos rápidos sustituyen los filtros anteriores. Los filtros se aplican en el servidor antes de paginar; cada página muestra hasta 50 expedientes. Las opciones inactivas permanecen disponibles para buscar registros históricos. Los filtros no pueden ampliar el acceso permitido por el rol.

Las tarjetas identifican **Objetivo vencido**, **Objetivo hoy** y **Objetivo en próximos 3 días** mediante texto. Son avisos dentro de la aplicación, no correos, notificaciones push ni alertas de vencimiento legal. Se actualizan al cargar la bandeja.

**Exportar página CSV** incluye los expedientes visibles con trámite y responsable. Omite documentos de identidad y contactos, y conserva la protección frente a fórmulas. Todavía no es un reporte de todos los resultados filtrados.

## Comprobaciones

El contrato `tests/work_queue_contract.sql` verifica clasificación, asignación, conservación de fichas, derivación, aislamiento por área, versiones obsoletas y restricciones de perfiles sobre PostgreSQL local. Los expedientes ficticios se revierten al finalizar y nunca se cargan en la base municipal.

Las pruebas de interfaz recorren registro, organización, derivación y accesos rápidos con Flet en anchos 390 y 1280. Se mantienen pendientes la revisión visual en Windows y las pruebas en dispositivos Android.
