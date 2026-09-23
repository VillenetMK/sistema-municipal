"""Pantallas de invitación, verificación de correo y recuperación de contraseña."""

import secrets
from uuid import uuid4

import flet as ft

from munigest.domain import ROLES, UserError
from munigest.ui import panel, small, timestamp


class AccountScreen:
    def __init__(self, app):
        self.app = app
        self.offset = 0

    def public_handler(self, kind):
        def handler(_):
            self.public_form(kind)

        return handler

    def guarded_handler(self, action):
        async def handler(_):
            await self.app.guard(action)

        return handler

    def public_form(self, kind, email_value=""):
        app = self.app
        email = ft.TextField(label="Correo de tu cuenta", value=email_value, max_length=254)
        code = ft.TextField(label="Código de invitación", password=True, can_reveal_password=True)
        verification = ft.TextField(
            label="Enlace original o código del correo", password=True, can_reveal_password=True
        )
        password = ft.TextField(
            label="Nueva contraseña (mínimo 12 caracteres)", password=True, can_reveal_password=True
        )
        confirmation = ft.TextField(
            label="Repetir contraseña", password=True, can_reveal_password=True
        )
        status = ft.Text("", selectable=True)

        async def send(e):
            async def work():
                if kind == "signup":
                    confirmed = await app.repo.activate_account(
                        email.value, code.value, password.value or "", confirmation.value or ""
                    )
                    code.value = password.value = confirmation.value = ""
                    if confirmed:
                        app.login()
                        app.notify("Cuenta activada. Ya puedes iniciar sesión.")
                    else:
                        self.public_form("confirm", email.value)
                        app.notify(
                            "Revisa tu correo para confirmar la cuenta. Si no llega, solicita un reenvío."
                        )
                elif kind == "confirm":
                    await app.repo.resend_confirmation(email.value)
                    status.value = "Si hay una confirmación pendiente, recibirás un correo. Revisa también spam."
                else:
                    await app.repo.request_recovery(email.value)
                    status.value = "Si el correo está registrado, recibirás instrucciones. Revisa también spam."

            await app.guard(work, e.control)

        async def verify(e):
            async def work():
                await app.repo.verify_account(
                    email.value,
                    verification.value,
                    "signup" if kind == "confirm" else "recovery",
                    password.value or "",
                    confirmation.value or "",
                )
                verification.value = password.value = confirmation.value = ""
                app.login()
                app.notify(
                    "Correo confirmado. Inicia sesión."
                    if kind == "confirm"
                    else "Contraseña actualizada. Inicia sesión nuevamente."
                )

            await app.guard(work, e.control)

        titles = {
            "signup": "Activar una invitación",
            "confirm": "Confirmar mi correo",
            "recovery": "Recuperar contraseña",
        }
        fields = [ft.Text(titles[kind], size=24, weight=ft.FontWeight.BOLD), email]
        if kind == "signup":
            fields += [
                small(
                    "El administrador te entrega una invitación válida durante 48 horas. Tus permisos ya están definidos."
                ),
                code,
                password,
                confirmation,
                ft.FilledButton("Crear mi cuenta", on_click=send),
            ]
        else:
            fields += [
                ft.OutlinedButton(
                    "Reenviar confirmación"
                    if kind == "confirm"
                    else "Solicitar correo de recuperación",
                    on_click=send,
                ),
                status,
                small(
                    "Copia el enlace del botón del correo sin abrirlo y pégalo aquí. Si el mensaje trae un código numérico, también puedes usarlo."
                ),
                verification,
            ]
            if kind == "recovery":
                fields += [password, confirmation]
            fields += [
                ft.FilledButton(
                    "Confirmar correo" if kind == "confirm" else "Guardar nueva contraseña",
                    on_click=verify,
                )
            ]
        fields += [ft.TextButton("Volver al inicio de sesión", on_click=lambda _: app.login())]
        app.page.controls.clear()
        app.page.add(
            ft.SafeArea(
                ft.Container(
                    ft.Column(
                        [panel(fields, width=520)],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=24,
                    expand=True,
                ),
                expand=True,
            )
        )
        app.page.update()

    async def show_invitations(self, _=None):
        app = self.app
        if app.settings.mode == "demo":
            raise UserError("Las invitaciones requieren una conexión real a Supabase.")
        rows = await app.repo.invitations(self.offset)

        async def create(_):
            await app.guard(self.invitation_form)

        async def previous(_):
            self.offset = max(0, self.offset - 50)
            await app.guard(self.show_invitations)

        async def next_page(_):
            self.offset += 50
            await app.guard(self.show_invitations)

        controls = [
            app.heading(
                "Invitaciones del personal",
                "El alta necesita un correo real. Las invitaciones pendientes se pueden revocar.",
            ),
            ft.Row(
                [
                    ft.FilledButton("Crear usuario", on_click=create),
                    ft.TextButton(
                        "Volver a Personal", on_click=self.guarded_handler(app.admin_screen.show)
                    ),
                ],
                wrap=True,
            ),
        ]
        for row in rows[:50]:
            state = (
                "Activada"
                if row["claimed_at"]
                else "Revocada"
                if row["revoked_at"]
                else "Pendiente; revisar vencimiento"
            )
            elements = [
                ft.Text(row["display_name"], size=18),
                small(f"{row['email']} · {ROLES[row['role']]}"),
                small(f"{state} · Vence: {timestamp(row['expires_at'])}"),
            ]
            if not row["claimed_at"] and not row["revoked_at"]:
                reason = ft.TextField(label="Motivo de revocación", max_length=500)

                async def revoke(e, invitation_id=row["id"], field=reason):
                    async def work():
                        await app.repo.revoke_invitation(invitation_id, field.value or "")
                        await self.show_invitations()

                    await app.guard(work, e.control)

                elements += [reason, ft.TextButton("Revocar invitación", on_click=revoke)]
            controls.append(panel(elements))
        if not rows:
            controls.append(small("Todavía no hay invitaciones."))
        controls.append(
            ft.Row(
                [
                    ft.TextButton("Anterior", disabled=self.offset == 0, on_click=previous),
                    small(f"Página {self.offset // 50 + 1}"),
                    ft.TextButton("Siguiente", disabled=len(rows) <= 50, on_click=next_page),
                ],
                wrap=True,
            )
        )
        app.content.controls = controls
        app.page.update()

    async def invitation_form(self):
        app = self.app
        areas = await app.repo.departments()
        name = ft.TextField(label="Nombre completo", max_length=120)
        email = ft.TextField(label="Correo real", max_length=254)
        role = ft.Dropdown(
            label="Rol",
            value="consulta",
            options=[ft.DropdownOption(k, v) for k, v in ROLES.items()],
        )
        area = ft.Dropdown(
            label="Área", options=[ft.DropdownOption(d["id"], d["name"]) for d in areas]
        )
        reason = ft.TextField(label="Motivo del alta", max_length=500)
        invitation_id, token = str(uuid4()), secrets.token_hex(32)

        async def save(e):
            async def work():
                row = await app.repo.create_invitation(
                    invitation_id,
                    token,
                    email=email.value,
                    name=name.value,
                    role=role.value,
                    department=area.value,
                    reason=reason.value,
                )
                app.content.controls = [
                    panel(
                        [
                            ft.Text("Invitación creada", size=24, weight=ft.FontWeight.BOLD),
                            small(
                                f"Para {row['email']} · {ROLES[row['role']]} · Vence: {timestamp(row['expires_at'])}"
                            ),
                            small(
                                "Entrega este código a la persona. En el inicio de sesión debe elegir «Activar invitación». El código solo se muestra aquí; si lo pierdes, revoca la invitación y crea otra."
                            ),
                            ft.TextField(
                                label="Código de invitación",
                                value=token,
                                read_only=True,
                                multiline=True,
                            ),
                            small(
                                "No se ha enviado un correo automático desde esta pantalla. La confirmación por correo se solicita cuando la persona activa su cuenta."
                            ),
                            ft.TextButton(
                                "Ver invitaciones",
                                on_click=self.guarded_handler(self.show_invitations),
                            ),
                        ]
                    )
                ]

            await app.guard(work, e.control)

        app.content.controls = [
            panel(
                [
                    ft.Text("Crear usuario por invitación", size=24),
                    name,
                    email,
                    role,
                    area,
                    reason,
                    ft.FilledButton("Crear invitación", on_click=save),
                    ft.TextButton("Cancelar", on_click=self.guarded_handler(self.show_invitations)),
                ]
            )
        ]
        app.page.update()
