import uuid

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.datastructures import UploadFile

from src.auth.dependencies import CsrfDep, CurrentUser, DbDep
from src.exceptions import BadRequestError
from src.kb import markdown as markdown_utils
from src.pagination import clamp_per_page, paginate
from src.templating import templates
from src.tickets import service as ticket_service
from src.tickets.constants import PAGE_SIZE
from src.tickets.dependencies import TicketDep, TicketEditor, TicketMember
from src.tickets.models import TicketPriority, TicketStatus
from src.users import service as users_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _parse_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _parse_status(value: object) -> TicketStatus | None:
    try:
        return TicketStatus(str(value))
    except ValueError:
        return None


def _parse_priority(value: object) -> TicketPriority | None:
    try:
        return TicketPriority(str(value))
    except ValueError:
        return None


async def _list_context(db, user, *, q, status_value, priority_value, category, assignee, sort, mine, page, per_page) -> dict:
    requester_id = user.id if mine or not ticket_service.is_editor(user) else None
    tickets, total = await ticket_service.list_tickets(
        db,
        user,
        q=q or None,
        status=_parse_status(status_value),
        priority=_parse_priority(priority_value),
        category_id=_parse_uuid(category),
        assignee_id=_parse_uuid(assignee),
        requester_id=requester_id,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    pag = paginate(page, per_page, total)
    return {
        "tickets": tickets,
        "sla_states": {ticket.id: ticket_service.sla_state(ticket) for ticket in tickets},
        "search": q or "",
        "status_filter": status_value or "",
        "priority_filter": priority_value or "",
        "category_filter": category or "",
        "assignee_filter": assignee or "",
        "sort": sort,
        "mine": mine,
        "is_editor": ticket_service.is_editor(user),
        "categories": await ticket_service.list_categories(db),
        "agents": await users_service.list_agents(db),
        "page": pag["page"],
        "per_page": per_page,
        "total_pages": pag["total_pages"],
        "total": pag["total"],
    }


# --------------------------------------------------------------------------- #
# List / create
# --------------------------------------------------------------------------- #
@router.get("")
async def ticket_list(
    request: Request,
    db: DbDep,
    user: CurrentUser,
    q: str = "",
    ticket_status: str = "",
    priority: str = "",
    category: str = "",
    assignee: str = "",
    sort: str = "updated",
    mine: str = "",
    page: int = 1,
    per_page: int = PAGE_SIZE,
):
    per_page = clamp_per_page(per_page)
    context = await _list_context(
        db,
        user,
        q=q,
        status_value=ticket_status,
        priority_value=priority,
        category=category,
        assignee=assignee,
        sort=sort,
        mine=mine,
        page=page,
        per_page=per_page,
    )
    return templates.TemplateResponse(request, "tickets/list.html", context)


@router.get("/partials/list")
async def ticket_list_partial(
    request: Request,
    db: DbDep,
    user: CurrentUser,
    q: str = "",
    ticket_status: str = "",
    priority: str = "",
    category: str = "",
    assignee: str = "",
    sort: str = "updated",
    mine: str = "",
    page: int = 1,
    per_page: int = PAGE_SIZE,
):
    per_page = clamp_per_page(per_page)
    context = await _list_context(
        db,
        user,
        q=q,
        status_value=ticket_status,
        priority_value=priority,
        category=category,
        assignee=assignee,
        sort=sort,
        mine=mine,
        page=page,
        per_page=per_page,
    )
    return templates.TemplateResponse(request, "tickets/partials/list.html", context)


@router.get("/new")
async def ticket_new(request: Request, db: DbDep, user: CurrentUser):
    return templates.TemplateResponse(request, "tickets/form.html", {"categories": await ticket_service.list_categories(db), "priorities": TicketPriority})


@router.post("")
async def ticket_create(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep):
    form = await request.form()
    subject = str(form.get("subject", "")).strip()
    if len(subject) < 3:
        raise BadRequestError(detail="Subject must be at least 3 characters")
    priority = _parse_priority(form.get("priority") or "normal")
    if priority is None:
        raise BadRequestError(detail="Invalid priority")
    ticket = await ticket_service.create_ticket(
        db,
        user,
        subject=subject,
        description=str(form.get("description", "")).strip(),
        category_id=_parse_uuid(form.get("category_id")),
        priority=priority,
    )
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Categories (static paths before /{ticket_id})
# --------------------------------------------------------------------------- #
@router.get("/categories")
async def categories_page(request: Request, db: DbDep, editor: TicketEditor):
    return templates.TemplateResponse(request, "tickets/categories/list.html", {"categories": await ticket_service.list_categories(db)})


@router.post("/categories")
async def create_category(request: Request, db: DbDep, editor: TicketEditor, _: CsrfDep):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        raise BadRequestError(detail="Name is required")
    position = int(str(form.get("position") or 0) or 0)
    await ticket_service.create_category(db, editor, name=name, position=position)
    return RedirectResponse("/tickets/categories", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/categories/{category_id}")
async def update_category(request: Request, db: DbDep, editor: TicketEditor, _: CsrfDep, category_id: uuid.UUID):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        raise BadRequestError(detail="Name is required")
    category = await ticket_service.get_category_by_id(db, category_id)
    position = int(str(form.get("position") or 0) or 0)
    await ticket_service.update_category(db, editor, category, name=name, position=position)
    return RedirectResponse("/tickets/categories", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/categories/{category_id}/delete")
async def delete_category(request: Request, db: DbDep, editor: TicketEditor, _: CsrfDep, category_id: uuid.UUID):
    category = await ticket_service.get_category_by_id(db, category_id)
    await ticket_service.delete_category(db, editor, category)
    return RedirectResponse("/tickets/categories", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/agents")
async def agents_json(db: DbDep, editor: TicketEditor):
    return JSONResponse([{"id": str(agent.id), "name": agent.name} for agent in await users_service.list_agents(db)])


# --------------------------------------------------------------------------- #
# Detail
# --------------------------------------------------------------------------- #
@router.get("/{ticket_id}")
async def ticket_detail(request: Request, db: DbDep, user: CurrentUser, ticket: TicketMember):
    timeline = await ticket_service.ticket_timeline(db, ticket, user)
    return templates.TemplateResponse(
        request,
        "tickets/detail.html",
        {
            "ticket": ticket,
            "timeline": timeline,
            "body_html": markdown_utils.render_markdown(ticket.description),
            "is_editor": ticket_service.is_editor(user),
            "sla": ticket_service.sla_state(ticket),
            "allowed_statuses": ticket_service.allowed_transitions(ticket, user),
            "agents": await users_service.list_agents(db),
            "categories": await ticket_service.list_categories(db),
            "related": await ticket_service.related_articles(db, ticket, user),
            "priorities": TicketPriority,
        },
    )


# --------------------------------------------------------------------------- #
# Comments
# --------------------------------------------------------------------------- #
@router.post("/{ticket_id}/comments")
async def add_comment(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, ticket: TicketMember):
    form = await request.form()
    body = str(form.get("body", "")).strip()
    if not body:
        raise BadRequestError(detail="Comment cannot be empty")
    is_internal = str(form.get("is_internal", "")) == "1"
    comment = await ticket_service.add_comment(db, user, ticket, body, is_internal=is_internal)
    upload = form.get("file")
    if isinstance(upload, UploadFile) and upload.filename:
        await ticket_service.add_attachment(db, user, ticket, upload, comment_id=comment.id)
    if request.headers.get("HX-Request") == "true":
        timeline = await ticket_service.ticket_timeline(db, ticket, user)
        return templates.TemplateResponse(
            request,
            "tickets/partials/timeline.html",
            {"ticket": ticket, "timeline": timeline, "is_editor": ticket_service.is_editor(user)},
        )
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ticket_id}/comments/{comment_id}/delete")
async def delete_comment(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, ticket: TicketMember, comment_id: uuid.UUID):
    from src.tickets.models import TicketComment

    comment = await db.get(TicketComment, comment_id)
    if comment is None or comment.ticket_id != ticket.id:
        raise BadRequestError(detail="Comment not found")
    await ticket_service.delete_comment(db, user, comment)
    if request.headers.get("HX-Request") == "true":
        timeline = await ticket_service.ticket_timeline(db, ticket, user)
        return templates.TemplateResponse(
            request,
            "tickets/partials/timeline.html",
            {"ticket": ticket, "timeline": timeline, "is_editor": ticket_service.is_editor(user)},
        )
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Workflow
# --------------------------------------------------------------------------- #
@router.post("/{ticket_id}/assign")
async def assign_ticket(request: Request, db: DbDep, editor: TicketEditor, _: CsrfDep, ticket: TicketDep):
    form = await request.form()
    assignee_id = _parse_uuid(form.get("assignee_id"))
    assignee = await users_service.get_user_by_id(db, assignee_id) if assignee_id else None
    await ticket_service.assign_ticket(db, editor, ticket, assignee)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ticket_id}/claim")
async def claim_ticket(request: Request, db: DbDep, editor: TicketEditor, _: CsrfDep, ticket: TicketDep):
    await ticket_service.claim_ticket(db, editor, ticket)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ticket_id}/status")
async def set_status(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, ticket: TicketMember):
    form = await request.form()
    target = _parse_status(form.get("status"))
    if target is None:
        raise BadRequestError(detail="Invalid status")
    await ticket_service.transition_status(db, user, ticket, target)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ticket_id}/priority")
async def set_priority(request: Request, db: DbDep, editor: TicketEditor, _: CsrfDep, ticket: TicketDep):
    form = await request.form()
    priority = _parse_priority(form.get("priority"))
    if priority is None:
        raise BadRequestError(detail="Invalid priority")
    await ticket_service.set_priority(db, editor, ticket, priority)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ticket_id}/close")
async def close_ticket(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, ticket: TicketMember):
    await ticket_service.transition_status(db, user, ticket, TicketStatus.CLOSED)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ticket_id}/reopen")
async def reopen_ticket(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, ticket: TicketMember):
    await ticket_service.transition_status(db, user, ticket, TicketStatus.OPEN)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Attachments
# --------------------------------------------------------------------------- #
@router.post("/{ticket_id}/attachments")
async def upload_attachment(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, ticket: TicketMember):
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile) or not upload.filename:
        raise BadRequestError(detail="No file provided")
    await ticket_service.add_attachment(db, user, ticket, upload)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{ticket_id}/attachments/{attachment_id}/delete")
async def remove_attachment(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, ticket: TicketMember, attachment_id: uuid.UUID):
    attachment = await ticket_service.get_attachment(db, ticket, attachment_id)
    await ticket_service.delete_attachment(db, user, attachment)
    return RedirectResponse(f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)
