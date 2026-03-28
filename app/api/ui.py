from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_roles
from app.core.templating import templates
from app.db.session import get_db
from app.models import (
    AssetObject,
    AuditLog,
    Document,
    DocumentType,
    Event,
    EventItem,
    EventUnit,
    Nomenclature,
    Service,
    Unit,
    User,
    Valuation,
    ValuationLink,
)
from app.models.enums import EventItemKind, EventStatus, ValuationKind
from app.services.audit_service import AuditService
from app.services.export_service import EventExportService
from app.services.file_storage import FileStorageService

router = APIRouter(tags=["ui"])


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    metrics = {
        "events": db.query(func.count(Event.id)).scalar() or 0,
        "documents": db.query(func.count(Document.id)).scalar() or 0,
        "users": db.query(func.count(User.id)).scalar() or 0,
    }
    return templates.TemplateResponse("dashboard.html", {"request": request, "current_user": user, "metrics": metrics})


@router.get("/events")
def events_list(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    events = db.query(Event).filter(Event.is_deleted.is_(False)).order_by(Event.event_date.desc()).all()
    return templates.TemplateResponse("events/list.html", {"request": request, "events": events, "current_user": user})


@router.post("/events")
def events_create(
    title: str = Form(...),
    event_date: str = Form(...),
    short_description: str = Form(""),
    location: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    event = Event(
        title=title,
        event_date=date.fromisoformat(event_date),
        short_description=short_description or None,
        location=location or None,
        status=EventStatus.DRAFT,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(event)
    db.flush()
    AuditService(db).log(entity_type="event", entity_id=str(event.id), action="create", user_id=user.id)
    db.commit()
    return RedirectResponse(url=f"/events/{event.id}", status_code=303)


@router.get("/events/{event_id}")
def event_detail(event_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = db.query(Event).filter(Event.id == event_id, Event.is_deleted.is_(False)).first()
    if not event:
        raise HTTPException(404)
    ctx = {
        "request": request,
        "event": event,
        "units": db.query(Unit).filter(Unit.is_deleted.is_(False)).all(),
        "services": db.query(Service).filter(Service.is_deleted.is_(False)).all(),
        "nomenclature": db.query(Nomenclature).filter(Nomenclature.is_deleted.is_(False)).all(),
        "asset_objects": db.query(AssetObject).filter(AssetObject.is_deleted.is_(False)).all(),
        "documents": db.query(Document).filter(Document.event_id == event_id, Document.is_deleted.is_(False)).all(),
        "doc_types": db.query(DocumentType).filter(DocumentType.is_deleted.is_(False)).all(),
        "valuations": db.query(Valuation).filter(Valuation.event_id == event_id, Valuation.is_deleted.is_(False)).all(),
        "event_units": db.query(EventUnit).filter(EventUnit.event_id == event_id).all(),
        "event_items": db.query(EventItem).filter(EventItem.event_id == event_id, EventItem.is_deleted.is_(False)).all(),
        "audit": db.query(AuditLog).filter(AuditLog.entity_id == str(event_id)).order_by(AuditLog.id.desc()).all(),
        "current_user": user,
        "valuation_kinds": list(ValuationKind),
    }
    return templates.TemplateResponse("events/detail.html", ctx)


@router.post("/events/{event_id}/units")
def add_event_unit(
    event_id: int,
    unit_id: int = Form(...),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    if is_primary:
        db.query(EventUnit).filter(EventUnit.event_id == event_id).update({"is_primary": False})
    db.add(EventUnit(event_id=event_id, unit_id=unit_id, is_primary=is_primary))
    AuditService(db).log(entity_type="event", entity_id=str(event_id), action="add_unit", user_id=user.id, diff={"unit_id": unit_id})
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/items")
def add_event_item(
    event_id: int,
    unit_id: int = Form(...),
    service_id: int = Form(...),
    kind: str = Form(...),
    qty: int = Form(...),
    asset_object_id: int | None = Form(None),
    nomenclature_id: int | None = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    if kind == EventItemKind.OBJECT.value:
        qty = 1
        if not asset_object_id:
            raise HTTPException(400, "asset_object_id is required")
        nomenclature_id = None
    elif kind == EventItemKind.GROUP.value:
        if qty <= 0 or not nomenclature_id:
            raise HTTPException(400, "group item requires qty>0 and nomenclature")
        asset_object_id = None
    else:
        raise HTTPException(400, "Invalid kind")

    item = EventItem(
        event_id=event_id,
        unit_id=unit_id,
        service_id=service_id,
        kind=EventItemKind(kind),
        qty=qty,
        asset_object_id=asset_object_id,
        nomenclature_id=nomenclature_id,
        notes=notes or None,
    )
    db.add(item)
    db.flush()
    AuditService(db).log(entity_type="event", entity_id=str(event_id), action="add_item", user_id=user.id, diff={"item_id": item.id})
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/documents")
async def add_document(
    event_id: int,
    document_type_id: int = Form(...),
    doc_no: str = Form(...),
    doc_date: str = Form(""),
    reg_date: str = Form(""),
    title: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    event_unit = db.query(EventUnit).filter(EventUnit.event_id == event_id, EventUnit.is_primary.is_(True)).first()
    doc_type = db.query(DocumentType).filter(DocumentType.id == document_type_id).first()
    unit_name = str(event_unit.unit_id) if event_unit else "unit"
    ext = Path(file.filename or "tmp.bin").suffix
    target_name = f"{date.today().isoformat()}__{unit_name}__{doc_type.code if doc_type else 'doc'}__No{doc_no}__reg_{reg_date or date.today().isoformat()}{ext}"

    try:
        stored = await FileStorageService().save_event_document(event_id=event_id, upload=file, target_name=target_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    doc = Document(
        event_id=event_id,
        document_type_id=document_type_id,
        doc_no=doc_no,
        doc_date=date.fromisoformat(doc_date) if doc_date else None,
        reg_date=date.fromisoformat(reg_date) if reg_date else None,
        title=title or None,
        file_path=stored.relative_path,
        sha256=stored.sha256,
        uploaded_by_id=user.id,
    )
    db.add(doc)
    db.flush()
    AuditService(db).log(entity_type="event", entity_id=str(event_id), action="add_document", user_id=user.id, diff={"document_id": doc.id})
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.get("/documents/{doc_id}/download")
def download_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.is_deleted.is_(False)).first()
    if not doc:
        raise HTTPException(404)
    path = FileStorageService().absolute(doc.file_path)
    return FileResponse(path)


@router.post("/events/{event_id}/valuations")
def add_valuation(
    event_id: int,
    valuation_kind: str = Form(...),
    date_effective: str = Form(...),
    document_id: int | None = Form(None),
    value_uah: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    valuation = Valuation(
        event_id=event_id,
        valuation_kind=ValuationKind(valuation_kind),
        document_id=document_id,
        date_effective=date.fromisoformat(date_effective),
        value_uah=Decimal(value_uah) if value_uah.strip() else None,
        notes=notes or None,
    )
    db.add(valuation)
    db.flush()
    AuditService(db).log(entity_type="event", entity_id=str(event_id), action="add_valuation", user_id=user.id, diff={"valuation_id": valuation.id})
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.post("/events/{event_id}/valuations/residual")
async def add_residual_valuation(
    event_id: int,
    request: Request,
    service_id: int = Form(...),
    date_effective: str = Form(...),
    value_uah: str = Form(...),
    document_id: int | None = Form(None),
    notes: str = Form(""),
    link_item_ids: list[int] = Form([]),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    form_data = await request.form()

    items = db.query(EventItem).filter(EventItem.event_id == event_id, EventItem.service_id == service_id, EventItem.is_deleted.is_(False)).all()
    allowed_qty = {item.id: item.qty for item in items}

    if not link_item_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one item for residual valuation")

    unique_item_ids: set[int] = set()
    links: list[tuple[int, int]] = []
    for item_id in link_item_ids:
        if item_id in unique_item_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate item in residual valuation request")
        unique_item_ids.add(item_id)

        if item_id not in allowed_qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Item {item_id} is not available for this service")

        raw_qty = str(form_data.get(f"qty_by_item_{item_id}", "")).strip()
        if not raw_qty:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Quantity is required for item {item_id}")
        try:
            qty = int(raw_qty)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Quantity for item {item_id} must be integer") from exc

        if qty <= 0 or qty > allowed_qty[item_id]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Quantity for item {item_id} must be in range 1..{allowed_qty[item_id]}")

        links.append((item_id, qty))

    valuation = Valuation(
        event_id=event_id,
        valuation_kind=ValuationKind.RESIDUAL_VALUE_STATEMENT,
        document_id=document_id,
        date_effective=date.fromisoformat(date_effective),
        value_uah=Decimal(value_uah),
        notes=notes or f"Residual for service {service_id}",
    )
    db.add(valuation)
    db.flush()

    for item_id, qty in links:
        db.add(ValuationLink(valuation_id=valuation.id, event_item_id=item_id, applies_qty=qty))

    AuditService(db).log(entity_type="event", entity_id=str(event_id), action="add_residual", user_id=user.id, diff={"valuation_id": valuation.id})
    db.commit()
    return RedirectResponse(f"/events/{event_id}", status_code=303)


@router.get("/events/{event_id}/export")
def export_event(event_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bundle = EventExportService(db).export_event(event_id)
    return FileResponse(bundle, filename=bundle.name)


def _dictionary_page(request: Request, db: Session, user: User, model, name: str, template: str):
    records = db.query(model).filter(model.is_deleted.is_(False)).order_by(model.code).all()
    return templates.TemplateResponse(template, {"request": request, "records": records, "name": name, "current_user": user})


@router.get("/dictionaries/units")
def units_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _dictionary_page(request, db, user, Unit, "units", "dictionaries/units.html")


@router.post("/dictionaries/units")
def units_create(code: str = Form(...), name: str = Form(...), parent_id: int | None = Form(None), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(Unit(code=code, name=name, parent_id=parent_id))
    db.commit()
    return RedirectResponse("/dictionaries/units", status_code=303)


@router.get("/dictionaries/services")
def services_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _dictionary_page(request, db, user, Service, "services", "dictionaries/services.html")


@router.post("/dictionaries/services")
def services_create(code: str = Form(...), name: str = Form(...), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(Service(code=code, name=name))
    db.commit()
    return RedirectResponse("/dictionaries/services", status_code=303)


@router.get("/dictionaries/nomenclature")
def nomenclature_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _dictionary_page(request, db, user, Nomenclature, "nomenclature", "dictionaries/nomenclature.html")


@router.post("/dictionaries/nomenclature")
def nomenclature_create(code: str = Form(...), name: str = Form(...), unit_of_measure: str = Form(""), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(Nomenclature(code=code, name=name, unit_of_measure=unit_of_measure or None))
    db.commit()
    return RedirectResponse("/dictionaries/nomenclature", status_code=303)


@router.get("/dictionaries/document-types")
def document_types_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _dictionary_page(request, db, user, DocumentType, "document types", "dictionaries/document_types.html")


@router.post("/dictionaries/document-types")
def document_types_create(code: str = Form(...), name: str = Form(...), default_extension: str = Form(""), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(DocumentType(code=code, name=name, default_extension=default_extension or None))
    db.commit()
    return RedirectResponse("/dictionaries/document-types", status_code=303)


@router.get("/users")
def users_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    users = db.query(User).filter(User.is_deleted.is_(False)).all()
    return templates.TemplateResponse("users/list.html", {"request": request, "users": users, "current_user": user})
