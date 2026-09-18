"""Demostración aislada en memoria. Nunca escribe datos ficticios en Supabase."""

import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from munigest.administration import ENTITIES, validate_admin_record
from munigest.domain import (
    STATUSES,
    UserError,
    clean_text,
    municipal_today,
    overdue,
    validate_attachment,
    validate_case_work,
    validate_draft,
    validate_transition,
)
from munigest.institution import (
    DEPARTMENT_DEFINITIONS,
    INSTITUTION_NAME,
    ORGANIZATION_URL,
    RECEPTION_URL,
    SERVICES_URL,
    TUPA_URL,
)
from munigest.reports import MAX_REPORT_ROWS, REPORT_LIMIT_MESSAGE, report_filters, search_term
from munigest.work_queue import eligible_workers, matches_filters

DEPARTMENTS = [
    {
        "id": f"10000000-0000-4000-8000-{index:012d}",
        "code": code,
        "name": name,
        "unit_type": unit_type,
        "source_url": RECEPTION_URL if code == "MP" else ORGANIZATION_URL,
        "is_active": True,
        "version": 1,
    }
    for index, (code, name, unit_type) in enumerate(DEPARTMENT_DEFINITIONS, start=1)
]


class DemoRepository:
    def __init__(self, seeded=True):
        self.profile = None
        self._cases = {}
        self._events = {}
        self._documents = {}
        self._requests = {}
        self._counter = 0
        self._departments = copy.deepcopy(DEPARTMENTS)
        self._procedures = [
            {
                "id": "30000000-0000-4000-8000-000000000001",
                "code": "GENERAL",
                "name": "Solicitud general",
                "requirements": "Documento de solicitud y anexos que correspondan.",
                "department_id": None,
                "is_official": False,
                "legal_basis": None,
                "fee_pen": None,
                "deadline_days": None,
                "is_active": True,
                "version": 1,
            }
        ]
        self._staff_profiles = [
            {
                "user_id": "20000000-0000-4000-8000-000000000001",
                "display_name": "Operador de demostración",
                "role": "admin",
                "department_id": DEPARTMENTS[0]["id"],
                "is_active": True,
                "version": 1,
            }
        ]
        self._admin_events = []
        if seeded:
            self._seed()

    def _seed(self):
        examples = [
            ("Solicitud de información sobre una obra pública", "GIP"),
            ("Consulta sobre licencia de funcionamiento", "GDEL"),
            ("Consulta sobre recolección de residuos sólidos", "GDA"),
            ("Presentación de documentación complementaria", "MP"),
            ("Solicitud de acceso a información pública", "GSG"),
            ("Consulta sobre programas sociales", "GDSPF"),
        ]
        for index, (title, department_code) in enumerate(examples):
            draft = {
                "title": title,
                "description": "Solicitud ficticia para explorar el flujo de atención. No corresponde a una persona real.",
                "document_type": "DNI",
                "document_number": f"{index + 1:08d}",
                "applicant_name": f"Solicitante de ejemplo {index + 1:02}",
                "department_id": next(d["id"] for d in DEPARTMENTS if d["code"] == department_code),
                "priority": "alta" if index == 0 else "normal",
                "channel": "presencial",
                "due_on": str(municipal_today() + timedelta(days=index - 2)),
                "request_id": str(uuid4()),
                "email": "",
                "phone": "",
            }
            item = self._create(draft)
            item["status"] = list(STATUSES)[index % 5]
            self._events[item["id"]][0]["to_status"] = item["status"]

    async def sign_in(self, *_):
        self.profile = copy.deepcopy(self._staff_profiles[0])
        return self.profile

    async def sign_out(self):
        self.profile = None

    async def close(self):
        await self.sign_out()

    async def departments(self, include_inactive=False):
        return copy.deepcopy([d for d in self._departments if include_inactive or d["is_active"]])

    async def settings(self):
        return {
            "institution_name": INSTITUTION_NAME,
            "configured": False,
            "official_website": SERVICES_URL,
            "organization_source_url": ORGANIZATION_URL,
            "tupa_source_url": TUPA_URL,
            "sources_checked_on": "2026-09-16",
        }

    async def procedures(self, include_inactive=False):
        return copy.deepcopy([p for p in self._procedures if include_inactive or p["is_active"]])

    async def staff_directory(self):
        return copy.deepcopy(self._staff_profiles)

    def _admin_actor(self):
        actor = next(
            (
                s
                for s in self._staff_profiles
                if self.profile and s["user_id"] == self.profile["user_id"]
            ),
            None,
        )
        if not actor or not actor["is_active"] or actor["role"] != "admin":
            raise UserError("Solo un administrador activo puede abrir Administración.")
        return actor

    async def admin_records(self, entity, query="", offset=0):
        self._admin_actor()
        if entity not in ENTITIES or offset < 0 or len(query) > 100:
            raise UserError("Sección, búsqueda o página inválida.")
        records = getattr(self, f"_{entity}")
        name_key = "display_name" if entity == "staff_profiles" else "name"
        rows = [
            r
            for r in records
            if query.strip().casefold() in (r[name_key] + " " + r.get("code", "")).casefold()
        ]
        rows.sort(key=lambda r: (r[name_key], r.get("id", r.get("user_id"))))
        return copy.deepcopy(rows[offset : offset + 51])

    async def admin_save(self, entity, raw, version, reason):
        actor = copy.deepcopy(self._admin_actor())
        data = validate_admin_record(entity, raw)
        reason = clean_text(reason, "Motivo", 10, 500)
        records = getattr(self, f"_{entity}")
        key = "user_id" if entity == "staff_profiles" else "id"
        old = next((r for r in records if r[key] == data[key]), None)
        if entity == "staff_profiles" and not old:
            raise UserError("La cuenta debe darse de alta antes de editar su perfil.")
        if version != (old["version"] if old else 0):
            raise UserError(
                "Otro usuario modificó el registro. Vuelve a la lista y abre la versión actual."
            )
        if entity != "staff_profiles" and any(
            r["code"] == data["code"] and r[key] != data[key] for r in records
        ):
            raise UserError("Ese código ya existe. Usa otro o edita el registro existente.")
        if (
            data["is_active"]
            and data.get("department_id")
            and not any(
                d["id"] == data["department_id"] and d["is_active"] for d in self._departments
            )
        ):
            raise UserError("Selecciona un área activa.")
        if (
            entity == "staff_profiles"
            and data[key] == actor["user_id"]
            and (not data["is_active"] or data["role"] != "admin")
        ):
            raise UserError(
                "No puedes desactivar tu propia cuenta ni retirar tu rol de administrador."
            )
        if entity == "departments" and not data["is_active"]:
            if any(
                r.get("department_id") == data[key] and r["is_active"]
                for r in self._staff_profiles + self._procedures
            ):
                raise UserError(
                    "Reasigna o desactiva primero el personal y los trámites activos de esta área."
                )
            if any(
                c["department_id"] == data[key] and c["status"] != "archivado"
                for c in self._cases.values()
            ):
                raise UserError(
                    "Esta área conserva expedientes sin archivar. Derívalos o concluye su archivo."
                )
        result = {**(old or {}), **data, "version": version + 1}
        if (
            entity == "staff_profiles"
            and old
            and (
                not data["is_active"]
                or data["role"] == "consulta"
                or data["department_id"] != old["department_id"]
            )
            and any(
                c.get("assigned_to") == data[key] and c["status"] not in {"atendido", "archivado"}
                for c in self._cases.values()
            )
        ):
            raise UserError("Reasigna o libera primero los expedientes pendientes de esta persona.")
        self._admin_events.append(
            {
                "id": len(self._admin_events) + 1,
                "entity": entity,
                "record_id": data[key],
                "actor_id": actor["user_id"],
                "actor_name": actor["display_name"],
                "reason": reason,
                "before_data": copy.deepcopy(old),
                "after_data": copy.deepcopy(result),
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        if old:
            old.update(result)
        else:
            records.append(result)
        return copy.deepcopy(result)

    async def admin_history(self, entity, record_id):
        self._admin_actor()
        return copy.deepcopy(
            [
                e
                for e in reversed(self._admin_events)
                if e["entity"] == entity and e["record_id"] == record_id
            ][:25]
        )

    async def metrics(self):
        values = list(self._cases.values())
        return {
            "total": len(values),
            "pending": sum(c["status"] not in {"atendido", "archivado"} for c in values),
            "overdue": sum(overdue(c) for c in values),
            "resolved": sum(c["status"] in {"atendido", "archivado"} for c in values),
        }

    async def list_cases(self, query="", status="", offset=0, limit=51, *, filters=None):
        query = search_term(query)
        rows = [
            x
            for x in self._cases.values()
            if (not status or x["status"] == status)
            and (
                not query
                or any(query.casefold() in x[k].casefold() for k in ("reference", "title"))
            )
            and matches_filters(x, filters, (self.profile or {}).get("user_id"))
        ]
        rows.sort(key=lambda x: (x["created_at"], x["id"]), reverse=True)
        return [self._with_assignee(c) for c in rows[offset : offset + limit]]

    def _export_actor(self):
        actor = next(
            (
                s
                for s in self._staff_profiles
                if self.profile and s["user_id"] == self.profile["user_id"]
            ),
            None,
        )
        if not actor or not actor["is_active"]:
            raise UserError("Inicia sesión con un perfil municipal activo.")
        return actor

    @staticmethod
    def _export_can_read(actor, case):
        return actor["role"] in {"admin", "mesa_partes"} or (
            actor["role"] in {"gestor", "consulta"}
            and actor.get("department_id") == case["department_id"]
        )

    async def case_report(self, query="", status="", *, filters=None):
        actor = self._export_actor()
        selected = report_filters(query, status, filters)
        at_time = datetime.now(UTC)
        from munigest.domain import MUNICIPAL_TZ

        today = at_time.astimezone(MUNICIPAL_TZ).date()
        rows = []
        for case in self._cases.values():
            if not self._export_can_read(actor, case):
                continue
            if selected["status"] and case["status"] != selected["status"]:
                continue
            if selected["query"] and not any(
                selected["query"].casefold() in case[k].casefold() for k in ("reference", "title")
            ):
                continue
            if not matches_filters(case, selected, actor["user_id"], today):
                continue
            item = self._with_assignee(case)
            rows.append(
                {
                    **{
                        k: item.get(k)
                        for k in (
                            "id",
                            "reference",
                            "title",
                            "status",
                            "priority",
                            "channel",
                            "created_at",
                            "due_on",
                            "version",
                            "department_id",
                            "procedure_id",
                            "assigned_to",
                        )
                    },
                    "department_name": item["department"]["name"],
                    "procedure_name": (item.get("procedure_snapshot") or {}).get("name"),
                    "assignee_name": (item.get("assignee") or {}).get("display_name"),
                }
            )
            if len(rows) > MAX_REPORT_ROWS:
                raise UserError(REPORT_LIMIT_MESSAGE)
        rows.sort(key=lambda row: (row["created_at"], row["id"]), reverse=True)
        area = next(
            (d["name"] for d in self._departments if d["id"] == actor.get("department_id")),
            "Sin área asignada",
        )
        return {
            "institution_name": INSTITUTION_NAME,
            "demo": True,
            "issued_at": at_time.isoformat(),
            "local_date": str(today),
            "issued_by": actor["display_name"],
            "scope": "Todos los expedientes" if actor["role"] in {"admin", "mesa_partes"} else area,
            "filters": selected,
            "filter_labels": {
                "department_id": next(
                    (d["name"] for d in self._departments if d["id"] == selected["department_id"]),
                    None,
                ),
                "procedure_id": next(
                    (p["name"] for p in self._procedures if p["id"] == selected["procedure_id"]),
                    None,
                ),
                "assignee": next(
                    (
                        s["display_name"]
                        for s in self._staff_profiles
                        if s["user_id"] == selected["assignee"]
                    ),
                    None,
                ),
            },
            "rows": rows,
        }

    async def case_receipt(self, case_id):
        actor = self._export_actor()
        item = self._cases.get(case_id)
        if not item or not self._export_can_read(actor, item):
            raise UserError("El expediente ya no está disponible en tu área. Actualiza la bandeja.")
        applicant = item["applicant"]
        number = applicant["document_number"]
        return {
            "institution_name": INSTITUTION_NAME,
            "demo": True,
            "issued_at": datetime.now(UTC).isoformat(),
            "case": {
                **{
                    k: item[k]
                    for k in (
                        "id",
                        "reference",
                        "title",
                        "description",
                        "channel",
                        "created_at",
                        "status",
                        "version",
                    )
                },
                "department_name": item["department"]["name"],
                "procedure_name": (item.get("procedure_snapshot") or {}).get("name"),
                "document_count": len(self._documents[case_id]),
                "applicant": {
                    "full_name": applicant["full_name"],
                    "document_type": applicant["document_type"],
                    "document_masked": "*" * max(0, len(number) - 4) + number[-4:],
                },
            },
        }

    async def get_case(self, case_id):
        return self._with_assignee(self._cases[case_id])

    def _with_assignee(self, case):
        result = copy.deepcopy(case)
        result["assignee"] = copy.deepcopy(
            next((s for s in self._staff_profiles if s["user_id"] == case.get("assigned_to")), None)
        )
        return result

    def _work_snapshot(self, case):
        fields = {
            k: copy.deepcopy(case.get(k))
            for k in ("procedure_id", "procedure_snapshot", "assigned_to", "priority", "due_on")
        }
        fields["assignee_name"] = (self._with_assignee(case)["assignee"] or {}).get("display_name")
        return fields

    def _check_assignee(self, assignee_id, department_id):
        if assignee_id and not any(
            s["user_id"] == assignee_id
            for s in eligible_workers(self._staff_profiles, department_id)
        ):
            raise UserError(
                "El responsable debe ser una persona activa con permiso de atención en esta área."
            )

    async def events(self, case_id):
        return copy.deepcopy(list(reversed(self._events[case_id])))

    def _create(self, draft):
        procedure = next(
            (
                p
                for p in self._procedures
                if p["is_active"]
                and (
                    p["id"] == draft.get("procedure_id")
                    if draft.get("procedure_id")
                    else p["code"] == "GENERAL"
                )
            ),
            None,
        )
        if not procedure:
            raise UserError("Selecciona un trámite activo del catálogo.")
        self._check_assignee(draft.get("assigned_to"), draft["department_id"])
        self._counter += 1
        now = datetime.now(UTC).isoformat()
        case_id = str(uuid4())
        item = {
            "id": case_id,
            "reference": f"DEMO-{municipal_today().year}-{self._counter:06d}",
            "status": "recibido",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            **draft,
            "procedure_id": procedure["id"],
            "procedure_snapshot": copy.deepcopy(procedure),
            "assigned_to": draft.get("assigned_to"),
            "department": next(x for x in self._departments if x["id"] == draft["department_id"]),
            "applicant": {
                "full_name": draft["applicant_name"],
                "document_type": draft["document_type"],
                "document_number": draft["document_number"],
                "email": draft["email"],
                "phone": draft["phone"],
            },
        }
        self._cases[case_id] = item
        self._events[case_id] = [
            {
                "created_at": now,
                "action": "registro",
                "actor_name": "Operador de demostración",
                "note": "Solicitud registrada en modo demostración.",
                "to_status": "recibido",
                "work_after": self._work_snapshot(item),
            }
        ]
        self._documents[case_id] = []
        return item

    async def create_case(self, raw):
        draft = validate_draft(raw)
        prior = self._requests.get(draft["request_id"])
        if prior:
            if prior[0] != draft:
                raise UserError(
                    "Este intento ya fue usado con otros datos. Abre un nuevo formulario."
                )
            return copy.deepcopy(prior[1])
        if not any(d["id"] == draft["department_id"] and d["is_active"] for d in self._departments):
            raise UserError("Selecciona un área activa.")
        item = self._create(draft)
        self._requests[draft["request_id"]] = (copy.deepcopy(draft), copy.deepcopy(item))
        return copy.deepcopy(item)

    async def advance_case(self, case, target, department_id, note):
        current = self._cases[case["id"]]
        if current["version"] != case["version"]:
            raise UserError("Otro usuario modificó el expediente. Actualiza antes de continuar.")
        note = validate_transition(
            current["status"], target, note, department_id == current["department_id"]
        )
        department = next(
            (x for x in self._departments if x["id"] == department_id and x["is_active"]), None
        )
        if department is None:
            raise UserError("Área de destino inválida.")
        before = self._work_snapshot(current)
        if department_id != current["department_id"]:
            current["assigned_to"] = None
        self._events[current["id"]].append(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "action": "actualización",
                "actor_name": "Operador de demostración",
                "note": note,
                "from_status": current["status"],
                "to_status": target,
                "work_before": before,
                "work_after": self._work_snapshot(current),
            }
        )
        current.update(
            status=target,
            department_id=department_id,
            department=department,
            version=current["version"] + 1,
        )
        return copy.deepcopy(current)

    async def set_case_work(self, case, raw):
        actor = next(
            (
                s
                for s in self._staff_profiles
                if self.profile and s["user_id"] == self.profile["user_id"]
            ),
            None,
        )
        current = self._cases[case["id"]]
        if not actor or not actor["is_active"] or actor["role"] == "consulta":
            raise UserError("Tu perfil no puede organizar expedientes.")
        if actor["role"] == "gestor" and actor["department_id"] != current["department_id"]:
            raise UserError("El expediente no está disponible para tu área.")
        if current["status"] in {"atendido", "archivado"}:
            raise UserError("El expediente ya está cerrado para organización.")
        if case["version"] != current["version"]:
            raise UserError("Otro usuario modificó el expediente. Actualiza antes de continuar.")
        data = validate_case_work(raw)
        note = data.pop("note")
        before = self._work_snapshot(current)
        if all(current.get(k) == v for k, v in data.items()):
            raise UserError(
                "Modifica el trámite, responsable, prioridad o fecha objetivo antes de guardar."
            )
        if data["procedure_id"] != current.get("procedure_id"):
            procedure = next(
                (p for p in self._procedures if p["id"] == data["procedure_id"] and p["is_active"]),
                None,
            )
            if not procedure:
                raise UserError("Selecciona un trámite activo del catálogo.")
            data["procedure_snapshot"] = copy.deepcopy(procedure)
        if data["assigned_to"] != current.get("assigned_to"):
            self._check_assignee(data["assigned_to"], current["department_id"])
        current.update(
            data, version=current["version"] + 1, updated_at=datetime.now(UTC).isoformat()
        )
        self._events[current["id"]].append(
            {
                "action": "organización",
                "actor_name": actor["display_name"],
                "to_status": current["status"],
                "created_at": datetime.now(UTC).isoformat(),
                "note": note,
                "work_before": before,
                "work_after": self._work_snapshot(current),
            }
        )
        return self._with_assignee(current)

    async def documents(self, case_id):
        return [{k: v for k, v in x.items() if k != "content"} for x in self._documents[case_id]]

    async def upload_document(self, case_id, filename, content):
        filename, mime = validate_attachment(filename, content)
        if self._cases[case_id]["status"] in {"atendido", "archivado"}:
            raise UserError("Este expediente ya está cerrado.")
        item = {
            "id": str(uuid4()),
            "case_id": case_id,
            "file_name": filename,
            "media_type": mime,
            "size_bytes": len(content),
            "content": content,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._documents[case_id].append(item)
        return {k: v for k, v in item.items() if k != "content"}

    async def download_document(self, document):
        return next(
            x["content"] for x in self._documents[document["case_id"]] if x["id"] == document["id"]
        )
