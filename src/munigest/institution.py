"""Identidad del piloto y referencias públicas de la MPCH; ver docs/CHICLAYO.md."""

APP_NAME = "MuniGest Chiclayo"
INSTITUTION_NAME = "Municipalidad Provincial de Chiclayo"
ORGANIZATION_URL = (
    "https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/6924346-organigrama-2024"
)
TUPA_URL = (
    "https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/"
    "7664214-texto-unico-de-procedimientos-administrativos-tupa-vigente-2026"
)
SERVICES_URL = "https://www.munichiclayo.gob.pe/serviciosonline/"
RECEPTION_URL = "https://www.munichiclayo.gob.pe/mpv/"

OFFICIAL_RESOURCES = (
    ("Consultar TUPA 2026", TUPA_URL),
    ("Consultar organigrama publicado", ORGANIZATION_URL),
    ("Abrir servicios digitales de la MPCH", SERVICES_URL),
)

# Subconjunto de destinos para el piloto, no una reproducción de todo el ROF.
# Los códigos son identificadores internos; no identificadores de la API del SGD.
# MP es un punto de recepción del piloto, no una gerencia del organigrama.
DEPARTMENT_DEFINITIONS = (
    ("MP", "Mesa de Partes", "punto_recepcion"),
    ("GM", "Gerencia Municipal", "gerencia"),
    ("GSG", "Gerencia de Secretaría General", "gerencia"),
    ("GAF", "Gerencia de Administración y Finanzas", "gerencia"),
    ("GRH", "Gerencia de Recursos Humanos", "gerencia"),
    ("GTIE", "Gerencia de Tecnologías de la Información y Estadística", "gerencia"),
    ("GAJ", "Gerencia de Asesoría Jurídica", "gerencia"),
    ("GPPM", "Gerencia de Planeamiento, Presupuesto y Modernización", "gerencia"),
    ("GDU", "Gerencia de Desarrollo Urbano", "gerencia"),
    ("GIP", "Gerencia de Infraestructura Pública", "gerencia"),
    ("GDSPF", "Gerencia de Desarrollo Social y Promoción de la Familia", "gerencia"),
    ("GDVT", "Gerencia de Desarrollo Vial y Transportes", "gerencia"),
    ("GSCF", "Gerencia de Seguridad Ciudadana y Fiscalización", "gerencia"),
    ("GDEL", "Gerencia de Desarrollo Económico Local", "gerencia"),
    ("GDA", "Gerencia de Desarrollo Ambiental", "gerencia"),
)

UNIT_TYPES = {
    "gerencia": "Gerencia",
    "punto_recepcion": "Punto de recepción del piloto",
    "referencia": "Área de referencia",
}
