"""Demostración aislada en memoria. Nunca escribe datos ficticios en Supabase."""

import copy
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from munigest.domain import (
    STATUSES,
    UserError,
    overdue,
    validate_attachment,
    validate_draft,
    validate_transition,
)

DEPARTMENTS = [
    {"id": "10000000-0000-4000-8000-000000000001", "code": "MP", "name": "Mesa de Partes"},
    {"id": "10000000-0000-4000-8000-000000000002", "code": "GM", "name": "Gerencia Municipal"},
    {"id": "10000000-0000-4000-8000-000000000003", "code": "AC", "name": "Atención al Ciudadano"},
]


class DemoRepository:
    def __init__(self, seeded=True):
        self.profile = None
        self._cases = {}
        self._events = {}
        self._documents = {}
        self._requests = {}
        self._counter = 0
        if seeded:
            self._seed()

    def _seed(self):
        titles = [
            "Solicitud de información sobre mantenimiento vial",
            "Consulta sobre licencia de funcionamiento",
            "Atención de incidencia en alumbrado público",
            "Presentación de documentación complementaria",
            "Solicitud de acceso a información pública",
            "Petición de reunión con atención al ciudadano",
        ]
        for index, title in enumerate(titles):
            draft = {
                "title": title,
                "description": "Solicitud ficticia para explorar el flujo de atención. No corresponde a una persona real.",
                "document_type": "DNI",
                "document_number": f"{index + 1:08d}",
                "applicant_name": f"Solicitante de ejemplo {index + 1:02}",
                "department_id": DEPARTMENTS[index % 3]["id"],
                "priority": "alta" if index == 0 else "normal",
                "channel": "presencial",
                "due_on": str(date.today() + timedelta(days=index - 2)),
                "request_id": str(uuid4()),
                "email": "",
                "phone": "",
            }
            item = self._create(draft)
            item["status"] = list(STATUSES)[index % 5]
            self._events[item["id"]][0]["to_status"] = item["status"]

    async def sign_in(self, *_):
        self.profile = {
            "user_id": "20000000-0000-4000-8000-000000000001",
            "display_name": "Operador de demostración",
            "role": "admin",
            "department_id": DEPARTMENTS[0]["id"],
            "is_active": True,
        }
        return self.profile

    async def sign_out(self):
        self.profile = None

    async def close(self):
        await self.sign_out()

    async def departments(self):
        return copy.deepcopy(DEPARTMENTS)

    async def settings(self):
        return {"institution_name": "Municipalidad · Demostración"}

    async def procedures(self):
        return [
            {
                "name": "Solicitud general",
                "code": "GENERAL",
                "requirements": "Documento de solicitud y anexos que correspondan.",
                "is_official": False,
                "legal_basis": None,
                "fee_pen": None,
                "deadline_days": None,
            }
        ]

    async def metrics(self):
        values = list(self._cases.values())
        return {
            "total": len(values),
            "pending": sum(c["status"] not in {"atendido", "archivado"} for c in values),
            "overdue": sum(overdue(c) for c in values),
            "resolved": sum(c["status"] in {"atendido", "archivado"} for c in values),
        }

    async def list_cases(self, query="", status="", offset=0, limit=51):
        rows = [
            x
            for x in self._cases.values()
            if (not status or x["status"] == status)
            and (not query or query.casefold() in (x["reference"] + " " + x["title"]).casefold())
        ]
        rows.sort(key=lambda x: (x["created_at"], x["id"]), reverse=True)
        return copy.deepcopy(rows[offset : offset + limit])

    async def get_case(self, case_id):
        return copy.deepcopy(self._cases[case_id])

    async def events(self, case_id):
        return copy.deepcopy(list(reversed(self._events[case_id])))

    def _create(self, draft):
        self._counter += 1
        now = datetime.now(UTC).isoformat()
        case_id = str(uuid4())
        item = {
            "id": case_id,
            "reference": f"DEMO-{date.today().year}-{self._counter:06d}",
            "status": "recibido",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            **draft,
            "department": next(x for x in DEPARTMENTS if x["id"] == draft["department_id"]),
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
        department = next((x for x in DEPARTMENTS if x["id"] == department_id), None)
        if department is None:
            raise UserError("Área de destino inválida.")
        self._events[current["id"]].append(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "action": "actualización",
                "actor_name": "Operador de demostración",
                "note": note,
                "from_status": current["status"],
                "to_status": target,
            }
        )
        current.update(
            status=target,
            department_id=department_id,
            department=department,
            version=current["version"] + 1,
        )
        return copy.deepcopy(current)

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
