from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user, require_roles
from app.auth.security import hash_password
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
    Role,
    Service,
    Unit,
    User,
    Valuation,
    ValuationLink,
)
from app.models.enums import AssetState, EventItemKind, EventStatus, ValuationKind
from app.services.audit_service import AuditService
from app.services.export_service import EventExportService
from app.services.file_storage import FileStorageService

router = APIRouter(tags=["ui"])


def _redirect(url: str, message: str = "") -> RedirectResponse:
    if message:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}msg={message}"
    return RedirectResponse(url=url, status_code=303)


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be valid date") from exc


def _event_or_404(db: Session, event_id: int) -> Event:
    event = db.query(Event).filter(Event.id == event_id, Event.is_deleted.is_(False)).first()
    if not event:
        raise HTTPException(404)
    return event


def _asset_or_404(db: Session, asset_id: int) -> AssetObject:
    asset = db.query(AssetObject).filter(AssetObject.id == asset_id, AssetObject.is_deleted.is_(False)).first()
    if not asset:
        raise HTTPException(404)
    return asset


def _active_admin_count(db: Session) -> int:
    return (
        db.query(func.count(User.id))
        .join(Role, User.role_id == Role.id)
        .filter(User.is_deleted.is_(False), User.is_active.is_(True), Role.code == "admin")
        .scalar()
        or 0
    )


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    metrics = {
        "events": db.query(func.count(Event.id)).filter(Event.is_deleted.is_(False)).scalar() or 0,
        "documents": db.query(func.count(Document.id)).filter(Document.is_deleted.is_(False)).scalar() or 0,
        "users": db.query(func.count(User.id)).filter(User.is_deleted.is_(False)).scalar() or 0,
    }
    return templates.TemplateResponse("dashboard.html", {"request": request, "current_user": user, "metrics": metrics})


@router.get("/events")
def events_list(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    events = (
        db.query(Event)
        .filter(Event.is_deleted.is_(False))
        .order_by(Event.event_date.desc(), Event.id.desc())
        .all()
    )
    return templates.TemplateResponse("events/list.html", {"request": request, "events": events, "current_user": user})


@router.post("/events")
def events_create(
    title: str = Form(...),
    event_date: str = Form(...),
    short_description: str = Form(""),
    location: str = Form(""),
    status_value: str = Form(EventStatus.DRAFT.value),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    if not title.strip():
        raise HTTPException(400, "Title is required")
    event = Event(
        title=title.strip(),
        event_date=_parse_date(event_date, "Event date"),
        short_description=short_description.strip() or None,
        location=location.strip() or None,
        status=EventStatus(status_value),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(event)
    db.flush()
    AuditService(db).log(
        entity_type="event",
        entity_id=str(event.id),
        action="create",
        user_id=user.id,
        description=f"Created event '{event.title}'",
    )
    db.commit()
    return _redirect(f"/events/{event.id}", "Event created")


@router.get("/events/{event_id}")
def event_detail(event_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    event = _event_or_404(db, event_id)
    ctx = {
        "request": request,
        "event": event,
        "units": db.query(Unit).filter(Unit.is_deleted.is_(False)).order_by(Unit.code).all(),
        "services": db.query(Service).filter(Service.is_deleted.is_(False)).order_by(Service.code).all(),
        "nomenclature": db.query(Nomenclature).filter(Nomenclature.is_deleted.is_(False)).order_by(Nomenclature.code).all(),
        "asset_objects": db.query(AssetObject).filter(AssetObject.is_deleted.is_(False)).order_by(AssetObject.id.desc()).all(),
        "documents": db.query(Document).filter(Document.event_id == event_id, Document.is_deleted.is_(False)).order_by(Document.id.desc()).all(),
        "doc_types": db.query(DocumentType).filter(DocumentType.is_deleted.is_(False)).order_by(DocumentType.code).all(),
        "valuations": db.query(Valuation).filter(Valuation.event_id == event_id, Valuation.is_deleted.is_(False)).order_by(Valuation.id.desc()).all(),
        "event_units": db.query(EventUnit).options(joinedload(EventUnit.unit)).filter(EventUnit.event_id == event_id).all(),
        "event_items": db.query(EventItem).filter(EventItem.event_id == event_id, EventItem.is_deleted.is_(False)).order_by(EventItem.id.desc()).all(),
        "unit_map": {u.id: f"{u.code} — {u.name}" for u in db.query(Unit).filter(Unit.is_deleted.is_(False)).all()},
        "service_map": {s.id: f"{s.code} — {s.name}" for s in db.query(Service).filter(Service.is_deleted.is_(False)).all()},
        "nomenclature_map": {n.id: f"{n.code} — {n.name}" for n in db.query(Nomenclature).filter(Nomenclature.is_deleted.is_(False)).all()},
        "audit": (
            db.query(AuditLog)
            .options(joinedload(AuditLog.user))
            .filter(AuditLog.entity_type == "event", AuditLog.entity_id == str(event_id))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .all()
        ),
        "current_user": user,
        "valuation_kinds": list(ValuationKind),
        "event_statuses": list(EventStatus),
    }
    return templates.TemplateResponse("events/detail.html", ctx)


@router.get("/events/{event_id}/edit")
def event_edit_page(event_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    event = _event_or_404(db, event_id)
    return templates.TemplateResponse(
        "events/edit.html",
        {"request": request, "event": event, "current_user": user, "event_statuses": list(EventStatus)},
    )


@router.post("/events/{event_id}/edit")
def event_edit(
    event_id: int,
    title: str = Form(...),
    event_date: str = Form(...),
    short_description: str = Form(""),
    location: str = Form(""),
    status_value: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    event = _event_or_404(db, event_id)
    old_status = event.status
    event.title = title.strip()
    event.event_date = _parse_date(event_date, "Event date")
    event.short_description = short_description.strip() or None
    event.location = location.strip() or None
    event.status = EventStatus(status_value)
    event.updated_by_id = user.id
    AuditService(db).log(
        entity_type="event",
        entity_id=str(event.id),
        action="update",
        user_id=user.id,
        description=f"Updated event '{event.title}'",
        diff={"status_from": old_status.value, "status_to": event.status.value},
    )
    if old_status != event.status:
        AuditService(db).log(
            entity_type="event",
            entity_id=str(event.id),
            action="status_change",
            user_id=user.id,
            description=f"Changed event status: {old_status.value} → {event.status.value}",
        )
    db.commit()
    return _redirect(f"/events/{event.id}", "Event updated")


@router.post("/events/{event_id}/units")
def add_event_unit(
    event_id: int,
    unit_id: int = Form(...),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    _event_or_404(db, event_id)
    existing = db.query(EventUnit).filter(EventUnit.event_id == event_id, EventUnit.unit_id == unit_id).first()
    if existing:
        return _redirect(f"/events/{event_id}", "Unit already linked")
    if is_primary:
        db.query(EventUnit).filter(EventUnit.event_id == event_id).update({"is_primary": False})
    db.add(EventUnit(event_id=event_id, unit_id=unit_id, is_primary=is_primary))
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    AuditService(db).log(
        entity_type="event",
        entity_id=str(event_id),
        action="add_unit",
        user_id=user.id,
        description=f"Linked unit {unit.code if unit else unit_id}",
        diff={"unit_id": unit_id},
    )
    db.commit()
    return _redirect(f"/events/{event_id}", "Unit added")


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
    event = _event_or_404(db, event_id)
    if event.status == EventStatus.CLOSED:
        raise HTTPException(400, "Closed event cannot be changed")

    if kind == EventItemKind.OBJECT.value:
        qty = 1
        if not asset_object_id:
            raise HTTPException(400, "Asset object is required")
        nomenclature_id = None
    elif kind == EventItemKind.GROUP.value:
        if qty <= 0 or not nomenclature_id:
            raise HTTPException(400, "Group item requires qty > 0 and nomenclature")
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
        notes=notes.strip() or None,
    )
    db.add(item)
    db.flush()
    AuditService(db).log(
        entity_type="event_item",
        entity_id=str(item.id),
        action="create",
        user_id=user.id,
        description=f"Added item #{item.id} to event #{event_id}",
        diff={"event_id": event_id},
    )
    db.commit()
    return _redirect(f"/events/{event_id}", "Item added")


@router.get("/events/{event_id}/items/{item_id}/edit")
def event_item_edit_page(event_id: int, item_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    item = db.query(EventItem).filter(EventItem.id == item_id, EventItem.event_id == event_id, EventItem.is_deleted.is_(False)).first()
    if not item:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "events/item_edit.html",
        {
            "request": request,
            "event": _event_or_404(db, event_id),
            "item": item,
            "units": db.query(Unit).filter(Unit.is_deleted.is_(False)).order_by(Unit.code).all(),
            "services": db.query(Service).filter(Service.is_deleted.is_(False)).order_by(Service.code).all(),
            "nomenclature": db.query(Nomenclature).filter(Nomenclature.is_deleted.is_(False)).order_by(Nomenclature.code).all(),
            "asset_objects": db.query(AssetObject).filter(AssetObject.is_deleted.is_(False)).order_by(AssetObject.id.desc()).all(),
            "current_user": user,
        },
    )


@router.post("/events/{event_id}/items/{item_id}/edit")
def event_item_edit(
    event_id: int,
    item_id: int,
    unit_id: int = Form(...),
    service_id: int = Form(...),
    qty: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    item = db.query(EventItem).filter(EventItem.id == item_id, EventItem.event_id == event_id, EventItem.is_deleted.is_(False)).first()
    if not item:
        raise HTTPException(404)
    if item.kind == EventItemKind.GROUP and qty <= 0:
        raise HTTPException(400, "Quantity must be positive")
    item.unit_id = unit_id
    item.service_id = service_id
    item.qty = 1 if item.kind == EventItemKind.OBJECT else qty
    item.notes = notes.strip() or None
    AuditService(db).log(
        entity_type="event_item",
        entity_id=str(item.id),
        action="update",
        user_id=user.id,
        description=f"Updated item #{item.id}",
        diff={"event_id": event_id},
    )
    db.commit()
    return _redirect(f"/events/{event_id}", "Item updated")


@router.post("/events/{event_id}/items/{item_id}/delete")
def event_item_delete(event_id: int, item_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    item = db.query(EventItem).filter(EventItem.id == item_id, EventItem.event_id == event_id, EventItem.is_deleted.is_(False)).first()
    if not item:
        raise HTTPException(404)
    linked_valuations = db.query(func.count(ValuationLink.id)).filter(ValuationLink.event_item_id == item_id).scalar() or 0
    if linked_valuations:
        raise HTTPException(400, "Cannot delete item linked to valuation")
    item.is_deleted = True
    AuditService(db).log(
        entity_type="event_item",
        entity_id=str(item.id),
        action="delete",
        user_id=user.id,
        description=f"Deleted item #{item.id}",
        diff={"event_id": event_id},
    )
    db.commit()
    return _redirect(f"/events/{event_id}", "Item removed")


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
    _event_or_404(db, event_id)
    if not doc_no.strip():
        raise HTTPException(400, "Document number is required")

    event_unit = db.query(EventUnit).options(joinedload(EventUnit.unit)).filter(EventUnit.event_id == event_id, EventUnit.is_primary.is_(True)).first()
    doc_type = db.query(DocumentType).filter(DocumentType.id == document_type_id).first()
    unit_name = event_unit.unit.code if event_unit and event_unit.unit else "unit"
    ext = Path(file.filename or "tmp.bin").suffix
    target_name = f"{date.today().isoformat()}__{unit_name}__{doc_type.code if doc_type else 'doc'}__No{doc_no.strip()}__reg_{reg_date or date.today().isoformat()}{ext}"

    try:
        stored = await FileStorageService().save_event_document(event_id=event_id, upload=file, target_name=target_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    doc = Document(
        event_id=event_id,
        document_type_id=document_type_id,
        doc_no=doc_no.strip(),
        doc_date=_parse_date(doc_date, "Doc date") if doc_date else None,
        reg_date=_parse_date(reg_date, "Reg date") if reg_date else None,
        title=title.strip() or None,
        file_path=stored.relative_path,
        sha256=stored.sha256,
        uploaded_by_id=user.id,
    )
    db.add(doc)
    db.flush()
    AuditService(db).log(
        entity_type="event",
        entity_id=str(event_id),
        action="add_document",
        user_id=user.id,
        description=f"Uploaded document #{doc.id} ({doc.doc_no})",
        diff={"document_id": doc.id},
    )
    db.commit()
    return _redirect(f"/events/{event_id}", "Document uploaded")


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
    parsed_value = None
    if value_uah.strip():
        try:
            parsed_value = Decimal(value_uah)
        except InvalidOperation as exc:
            raise HTTPException(400, "Value must be numeric") from exc

    valuation = Valuation(
        event_id=event_id,
        valuation_kind=ValuationKind(valuation_kind),
        document_id=document_id,
        date_effective=_parse_date(date_effective, "Effective date"),
        value_uah=parsed_value,
        notes=notes.strip() or None,
    )
    db.add(valuation)
    db.flush()
    AuditService(db).log(
        entity_type="event",
        entity_id=str(event_id),
        action="add_valuation",
        user_id=user.id,
        description=f"Created valuation #{valuation.id}",
        diff={"valuation_id": valuation.id},
    )
    db.commit()
    return _redirect(f"/events/{event_id}", "Valuation added")


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
        date_effective=_parse_date(date_effective, "Effective date"),
        value_uah=Decimal(value_uah),
        notes=notes or f"Residual for service {service_id}",
    )
    db.add(valuation)
    db.flush()

    for item_id, qty in links:
        db.add(ValuationLink(valuation_id=valuation.id, event_item_id=item_id, applies_qty=qty))

    AuditService(db).log(
        entity_type="event",
        entity_id=str(event_id),
        action="add_residual",
        user_id=user.id,
        description=f"Created residual valuation #{valuation.id}",
        diff={"valuation_id": valuation.id},
    )
    db.commit()
    return _redirect(f"/events/{event_id}", "Residual valuation saved")


@router.get("/events/{event_id}/export")
def export_event(event_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bundle = EventExportService(db).export_event(event_id)
    return FileResponse(bundle, filename=bundle.name)


@router.get("/asset-objects")
def asset_objects_list(request: Request, q: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(AssetObject, Nomenclature).join(Nomenclature, AssetObject.nomenclature_id == Nomenclature.id).filter(AssetObject.is_deleted.is_(False))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            AssetObject.inventory_number.ilike(like)
            | AssetObject.serial_number.ilike(like)
            | AssetObject.vin.ilike(like)
            | Nomenclature.name.ilike(like)
        )
    assets = query.order_by(AssetObject.id.desc()).all()
    return templates.TemplateResponse("assets/list.html", {"request": request, "assets": assets, "q": q, "current_user": user})


@router.get("/asset-objects/new")
def asset_object_new_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    nomenclature = db.query(Nomenclature).filter(Nomenclature.is_deleted.is_(False)).order_by(Nomenclature.code).all()
    return templates.TemplateResponse("assets/form.html", {"request": request, "asset": None, "nomenclature": nomenclature, "states": list(AssetState), "current_user": user})


@router.post("/asset-objects/new")
def asset_object_create(
    nomenclature_id: int = Form(...),
    inventory_number: str = Form(""),
    serial_number: str = Form(""),
    vin: str = Form(""),
    plate_number: str = Form(""),
    state: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    if not (inventory_number.strip() or serial_number.strip() or vin.strip()):
        raise HTTPException(400, "At least one accounting identifier is required")
    asset = AssetObject(
        nomenclature_id=nomenclature_id,
        inventory_number=inventory_number.strip() or None,
        serial_number=serial_number.strip() or None,
        vin=vin.strip() or None,
        plate_number=plate_number.strip() or None,
        state=AssetState(state) if state else None,
        notes=notes.strip() or None,
    )
    db.add(asset)
    db.flush()
    AuditService(db).log(
        entity_type="asset_object",
        entity_id=str(asset.id),
        action="create",
        user_id=user.id,
        description=f"Created asset object #{asset.id}",
    )
    db.commit()
    return _redirect(f"/asset-objects/{asset.id}", "Asset object created")


@router.get("/asset-objects/{asset_id}")
def asset_object_detail(asset_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    asset = _asset_or_404(db, asset_id)
    nomenclature = db.query(Nomenclature).filter(Nomenclature.id == asset.nomenclature_id).first()
    usage_count = db.query(func.count(EventItem.id)).filter(EventItem.asset_object_id == asset_id, EventItem.is_deleted.is_(False)).scalar() or 0
    return templates.TemplateResponse(
        "assets/detail.html",
        {"request": request, "asset": asset, "nomenclature": nomenclature, "usage_count": usage_count, "current_user": user},
    )


@router.get("/asset-objects/{asset_id}/edit")
def asset_object_edit_page(asset_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    asset = _asset_or_404(db, asset_id)
    nomenclature = db.query(Nomenclature).filter(Nomenclature.is_deleted.is_(False)).order_by(Nomenclature.code).all()
    return templates.TemplateResponse("assets/form.html", {"request": request, "asset": asset, "nomenclature": nomenclature, "states": list(AssetState), "current_user": user})


@router.post("/asset-objects/{asset_id}/edit")
def asset_object_update(
    asset_id: int,
    nomenclature_id: int = Form(...),
    inventory_number: str = Form(""),
    serial_number: str = Form(""),
    vin: str = Form(""),
    plate_number: str = Form(""),
    state: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    asset = _asset_or_404(db, asset_id)
    if not (inventory_number.strip() or serial_number.strip() or vin.strip()):
        raise HTTPException(400, "At least one accounting identifier is required")
    asset.nomenclature_id = nomenclature_id
    asset.inventory_number = inventory_number.strip() or None
    asset.serial_number = serial_number.strip() or None
    asset.vin = vin.strip() or None
    asset.plate_number = plate_number.strip() or None
    asset.state = AssetState(state) if state else None
    asset.notes = notes.strip() or None
    AuditService(db).log(
        entity_type="asset_object",
        entity_id=str(asset.id),
        action="update",
        user_id=user.id,
        description=f"Updated asset object #{asset.id}",
    )
    db.commit()
    return _redirect(f"/asset-objects/{asset.id}", "Asset object updated")


@router.post("/asset-objects/{asset_id}/deactivate")
def asset_object_deactivate(asset_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    asset = _asset_or_404(db, asset_id)
    asset.is_deleted = True
    AuditService(db).log(
        entity_type="asset_object",
        entity_id=str(asset.id),
        action="deactivate",
        user_id=user.id,
        description=f"Deactivated asset object #{asset.id}",
    )
    db.commit()
    return _redirect("/asset-objects", "Asset object deactivated")


@router.get("/dictionaries/units")
def units_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = db.query(Unit).filter(Unit.is_deleted.is_(False)).order_by(Unit.code).all()
    return templates.TemplateResponse("dictionaries/units.html", {"request": request, "records": records, "name": "units", "current_user": user})


@router.post("/dictionaries/units")
def units_create(code: str = Form(...), name: str = Form(...), parent_id: int | None = Form(None), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(Unit(code=code.strip(), name=name.strip(), parent_id=parent_id))
    db.commit()
    return _redirect("/dictionaries/units", "Unit created")


@router.get("/dictionaries/services")
def services_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = db.query(Service).filter(Service.is_deleted.is_(False)).order_by(Service.code).all()
    return templates.TemplateResponse("dictionaries/services.html", {"request": request, "records": records, "name": "services", "current_user": user})


@router.post("/dictionaries/services")
def services_create(code: str = Form(...), name: str = Form(...), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(Service(code=code.strip(), name=name.strip()))
    db.commit()
    return _redirect("/dictionaries/services", "Service created")


@router.get("/dictionaries/nomenclature")
def nomenclature_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = db.query(Nomenclature).filter(Nomenclature.is_deleted.is_(False)).order_by(Nomenclature.code).all()
    return templates.TemplateResponse("dictionaries/nomenclature.html", {"request": request, "records": records, "name": "nomenclature", "current_user": user})


@router.post("/dictionaries/nomenclature")
def nomenclature_create(code: str = Form(...), name: str = Form(...), unit_of_measure: str = Form(""), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(Nomenclature(code=code.strip(), name=name.strip(), unit_of_measure=unit_of_measure.strip() or None))
    db.commit()
    return _redirect("/dictionaries/nomenclature", "Nomenclature created")


@router.get("/dictionaries/document-types")
def document_types_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = db.query(DocumentType).filter(DocumentType.is_deleted.is_(False)).order_by(DocumentType.code).all()
    return templates.TemplateResponse("dictionaries/document_types.html", {"request": request, "records": records, "name": "document types", "current_user": user})


@router.post("/dictionaries/document-types")
def document_types_create(code: str = Form(...), name: str = Form(...), default_extension: str = Form(""), db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "operator"))):
    db.add(DocumentType(code=code.strip(), name=name.strip(), default_extension=default_extension.strip() or None))
    db.commit()
    return _redirect("/dictionaries/document-types", "Document type created")


@router.get("/users")
def users_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    users = db.query(User).options(joinedload(User.role)).filter(User.is_deleted.is_(False)).order_by(User.id).all()
    return templates.TemplateResponse("users/list.html", {"request": request, "users": users, "current_user": user})


@router.get("/users/new")
def user_new_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    roles = db.query(Role).order_by(Role.code).all()
    return templates.TemplateResponse("users/form.html", {"request": request, "managed_user": None, "roles": roles, "current_user": user})


@router.post("/users/new")
def user_create(
    username: str = Form(...),
    full_name: str = Form(""),
    role_id: int = Form(...),
    password: str = Form(...),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    if db.query(User).filter(User.username == username.strip(), User.is_deleted.is_(False)).first():
        raise HTTPException(400, "Username already exists")
    if not password.strip():
        raise HTTPException(400, "Password is required")

    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(400, "Role does not exist")

    created = User(
        username=username.strip(),
        full_name=full_name.strip() or None,
        role_id=role_id,
        password_hash=hash_password(password),
        is_active=is_active,
    )
    db.add(created)
    db.flush()
    AuditService(db).log(
        entity_type="user",
        entity_id=str(created.id),
        action="create",
        user_id=user.id,
        description=f"Created user {created.username}",
    )
    db.commit()
    return _redirect("/users", "User created")


@router.get("/users/{target_user_id}/edit")
def user_edit_page(target_user_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    target = db.query(User).filter(User.id == target_user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(404)
    roles = db.query(Role).order_by(Role.code).all()
    return templates.TemplateResponse("users/form.html", {"request": request, "managed_user": target, "roles": roles, "current_user": user})


@router.post("/users/{target_user_id}/edit")
def user_edit(
    target_user_id: int,
    username: str = Form(...),
    full_name: str = Form(""),
    role_id: int = Form(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    target = db.query(User).options(joinedload(User.role)).filter(User.id == target_user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(404)

    existing = db.query(User).filter(User.username == username.strip(), User.id != target_user_id, User.is_deleted.is_(False)).first()
    if existing:
        raise HTTPException(400, "Username already exists")

    new_role = db.query(Role).filter(Role.id == role_id).first()
    if not new_role:
        raise HTTPException(400, "Role does not exist")

    was_admin_and_active = target.role.code == "admin" and target.is_active
    will_be_admin_and_active = new_role.code == "admin" and is_active
    if was_admin_and_active and not will_be_admin_and_active and _active_admin_count(db) <= 1:
        raise HTTPException(400, "Cannot remove the last active admin")

    old_role = target.role.code
    old_active = target.is_active
    target.username = username.strip()
    target.full_name = full_name.strip() or None
    target.role_id = role_id
    target.is_active = is_active

    AuditService(db).log(
        entity_type="user",
        entity_id=str(target.id),
        action="update",
        user_id=user.id,
        description=f"Updated user {target.username}",
    )
    if old_role != new_role.code:
        AuditService(db).log(
            entity_type="user",
            entity_id=str(target.id),
            action="role_change",
            user_id=user.id,
            description=f"Role changed for {target.username}: {old_role} → {new_role.code}",
        )
    if old_active != is_active:
        AuditService(db).log(
            entity_type="user",
            entity_id=str(target.id),
            action="activation_change",
            user_id=user.id,
            description=f"User {target.username} {'activated' if is_active else 'deactivated'}",
        )

    db.commit()
    return _redirect("/users", "User updated")


@router.post("/users/{target_user_id}/password")
def user_change_password(
    target_user_id: int,
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    if not password.strip():
        raise HTTPException(400, "Password cannot be empty")
    target = db.query(User).filter(User.id == target_user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(404)
    target.password_hash = hash_password(password)
    AuditService(db).log(
        entity_type="user",
        entity_id=str(target.id),
        action="password_change",
        user_id=user.id,
        description=f"Password updated for {target.username}",
    )
    db.commit()
    return _redirect(f"/users/{target_user_id}/edit", "Password changed")


@router.get("/audit")
def audit_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    records = db.query(AuditLog).options(joinedload(AuditLog.user)).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(500).all()
    return templates.TemplateResponse("audit/list.html", {"request": request, "records": records, "current_user": user})
