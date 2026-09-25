"""Lenguaje visual común: contraste, ritmo y estados reconocibles sin color."""

import flet as ft

INK = "#172D32"
MUTED = "#52656B"
LINE = "#D9E2E4"
SURFACE = "#F3F6F6"
ACCENT = "#17665E"
SOFT = "#EAF2F0"
WHITE = "#FFFFFF"

STATUS_ICONS = {
    "recibido": ft.Icons.INBOX_OUTLINED,
    "en_revision": ft.Icons.MANAGE_SEARCH_OUTLINED,
    "observado": ft.Icons.INFO_OUTLINE,
    "atendido": ft.Icons.TASK_ALT,
    "archivado": ft.Icons.INVENTORY_2_OUTLINED,
}


def theme():
    button = dict(
        shape=ft.RoundedRectangleBorder(radius=10),
        padding=ft.Padding.symmetric(horizontal=18, vertical=12),
        text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
        icon_size=19,
    )
    return ft.Theme(
        color_scheme_seed=ACCENT,
        use_material3=True,
        font_family="Roboto",
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            on_primary=WHITE,
            primary_container=SOFT,
            on_primary_container=INK,
            surface=WHITE,
            on_surface=INK,
            on_surface_variant=MUTED,
            outline="#86999E",
            outline_variant=LINE,
            surface_tint=WHITE,
        ),
        text_theme=ft.TextTheme(
            body_large=ft.TextStyle(size=15, color=INK),
            body_medium=ft.TextStyle(size=14, color=INK),
            body_small=ft.TextStyle(size=12, color=MUTED),
            title_medium=ft.TextStyle(size=16, weight=ft.FontWeight.W_600, color=INK),
            label_large=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
        ),
        filled_button_theme=ft.FilledButtonTheme(style=ft.ButtonStyle(**button)),
        outlined_button_theme=ft.OutlinedButtonTheme(
            style=ft.ButtonStyle(**button, side=ft.BorderSide(1, LINE))
        ),
        text_button_theme=ft.TextButtonTheme(style=ft.ButtonStyle(**button)),
        divider_color=LINE,
    )


def style_fields(control):
    """Aplicar el mismo aspecto sin cambiar validaciones, valores ni manejadores."""
    if isinstance(control, (ft.TextField, ft.Dropdown)):
        if control.border is None:
            control.border = {
                ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                    border_radius=10, side=ft.BorderSide(1, "#86999E")
                ),
                ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                    border_radius=10, side=ft.BorderSide(2, ACCENT)
                ),
            }
        control.filled = True
        control.fill_color = "#FAFCFC"
        control.text_size = 14
        control.label_style = ft.TextStyle(size=13, color=MUTED)
        control.content_padding = ft.Padding.symmetric(horizontal=14, vertical=16)
        control.counter_style = ft.TextStyle(size=11, color=MUTED)
    for child in getattr(control, "controls", []) or []:
        style_fields(child)
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        style_fields(content)
    return control


def small(text):
    return ft.Text(text, size=13, color=MUTED)


def panel(controls, **kwargs):
    # Campos y textos aprovechan el ancho; las acciones mantienen un ancho natural.
    children = [
        ft.Row([c], wrap=True)
        if isinstance(c, (ft.FilledButton, ft.OutlinedButton, ft.TextButton))
        and c.width != float("inf")
        else c
        for c in controls
    ]
    options = dict(
        bgcolor=WHITE,
        border=ft.Border.all(1, LINE),
        border_radius=16,
        padding=20,
    )
    options.update(kwargs)
    return style_fields(
        ft.Container(
            ft.Column(children, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            **options,
        )
    )


def icon_badge(icon, *, dark=False, size=40):
    return ft.Container(
        ft.Icon(icon, size=20, color=WHITE if dark else ACCENT),
        width=size,
        height=size,
        alignment=ft.Alignment.CENTER,
        bgcolor="#29474C" if dark else SOFT,
        border_radius=12,
    )


def pill(text, icon=None):
    return ft.Container(
        ft.Row(
            ([ft.Icon(icon, size=14, color=INK)] if icon else [])
            + [ft.Text(text, size=12, weight=ft.FontWeight.W_600, color=INK)],
            spacing=6,
            tight=True,
        ),
        bgcolor=SOFT,
        border=ft.Border.all(1, LINE),
        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
        border_radius=8,
    )


def section(title, icon, subtitle=None):
    texts = [ft.Text(title, size=17, weight=ft.FontWeight.W_600, color=INK)]
    if subtitle:
        texts.append(small(subtitle))
    return ft.Row([icon_badge(icon, size=36), ft.Column(texts, spacing=3, expand=True)], spacing=12)


def metric(label, value, icon, caption, *, featured=False):
    return ft.Container(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            label,
                            size=13,
                            weight=ft.FontWeight.W_500,
                            color=WHITE if featured else MUTED,
                            expand=True,
                        ),
                        ft.Icon(icon, size=19, color=WHITE if featured else ACCENT),
                    ],
                    spacing=6,
                ),
                ft.Text(
                    str(value),
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=WHITE if featured else INK,
                ),
                ft.Text(caption, size=11, color="#D6E7E4" if featured else MUTED),
            ],
            spacing=8,
        ),
        col={"xs": 6, "md": 3},
        padding=18,
        border=ft.Border.all(1, INK if featured else LINE),
        border_radius=16,
        bgcolor=INK if featured else WHITE,
    )


def brand(name="MuniGest Chiclayo"):
    return ft.Row(
        [
            icon_badge(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=44),
            ft.Column(
                [
                    ft.Text(name, size=21, weight=ft.FontWeight.BOLD, color=INK),
                    ft.Text("MESA DE PARTES · GESTIÓN INTERNA", size=10, color=MUTED),
                ],
                spacing=3,
                expand=True,
            ),
        ],
        spacing=12,
    )
