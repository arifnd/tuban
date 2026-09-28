import uuid

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from starlette.datastructures import UploadFile

from src.auth.dependencies import CurrentUser, DbDep, OptionalUser
from src.exceptions import BadRequestError
from src.kb import markdown as markdown_utils
from src.kb import service as kb_service
from src.kb.constants import PAGE_SIZE
from src.kb.dependencies import KbEditor
from src.kb.models import KbArticleStatus, KbArticleVisibility
from src.pagination import Page, clamp_per_page, paginate
from src.templating import templates

router = APIRouter(prefix="/kb", tags=["kb"])


def _parse_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _parse_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return default


def _parse_visibility(value: object) -> KbArticleVisibility:
    try:
        return KbArticleVisibility(str(value))
    except ValueError:
        return KbArticleVisibility.INTERNAL


def _parse_status(value: object) -> KbArticleStatus | None:
    try:
        return KbArticleStatus(str(value))
    except ValueError:
        return None


def _parse_tags(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


async def _filter_category_id(db, slug: str | None) -> uuid.UUID | None:
    if not slug:
        return None
    category = await kb_service.get_category_by_slug(db, slug)
    return category.id


async def _filter_tag_id(db, slug: str | None) -> uuid.UUID | None:
    if not slug:
        return None
    tag = await kb_service.get_tag_by_slug(db, slug)
    return tag.id


# --------------------------------------------------------------------------- #
# Home
# --------------------------------------------------------------------------- #
@router.get("")
async def home(request: Request, db: DbDep, user: OptionalUser):
    categories = await kb_service.list_categories(db, viewer=user)
    category_sections = []
    for category in categories:
        articles = await kb_service.list_articles(db, user, category_id=category.id, offset=0, limit=5)
        if articles:
            category_sections.append({"category": category, "articles": articles})
    return templates.TemplateResponse(
        request,
        "kb/home.html",
        {
            "recent": await kb_service.recent_articles(db, user, 5),
            "popular": await kb_service.popular_articles(db, user, 5),
            "category_sections": category_sections,
        },
    )


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
@router.get("/categories")
async def categories_page(request: Request, db: DbDep, editor: KbEditor):
    return templates.TemplateResponse(request, "kb/categories/list.html", {"categories": await kb_service.list_categories(db)})


@router.post("/categories")
async def create_category(request: Request, db: DbDep, editor: KbEditor):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        raise BadRequestError(detail="Name is required")
    await kb_service.create_category(db, editor, name=name, description=str(form.get("description", "")).strip(), position=_parse_int(form.get("position")))
    return RedirectResponse("/kb/categories", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/categories/{category_id}")
async def update_category(request: Request, db: DbDep, editor: KbEditor, category_id: uuid.UUID):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        raise BadRequestError(detail="Name is required")
    category = await kb_service.get_category_by_id(db, category_id)
    await kb_service.update_category(
        db, editor, category, name=name, description=str(form.get("description", "")).strip(), position=_parse_int(form.get("position"))
    )
    return RedirectResponse("/kb/categories", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/categories/{category_id}/delete")
async def delete_category(request: Request, db: DbDep, editor: KbEditor, category_id: uuid.UUID):
    category = await kb_service.get_category_by_id(db, category_id)
    await kb_service.delete_category(db, editor, category)
    return RedirectResponse("/kb/categories", status_code=status.HTTP_303_SEE_OTHER)


# --------------------------------------------------------------------------- #
# Articles
# --------------------------------------------------------------------------- #
@router.get("/articles")
async def article_list(
    request: Request,
    db: DbDep,
    user: OptionalUser,
    q: str = "",
    category: str = "",
    tag: str = "",
    article_status: str = "",
    page: int = 1,
    per_page: int = PAGE_SIZE,
):
    per_page = clamp_per_page(per_page)
    article_status_value = _parse_status(article_status) if kb_service.is_editor(user) else None
    category_id = await _filter_category_id(db, category)
    tag_id = await _filter_tag_id(db, tag)
    total = await kb_service.count_articles(db, user, q=q.strip() or None, category_id=category_id, tag_id=tag_id, status=article_status_value)
    pag = paginate(page, per_page, total)
    articles = await kb_service.list_articles(
        db,
        user,
        q=q.strip() or None,
        category_id=category_id,
        tag_id=tag_id,
        status=article_status_value,
        offset=pag["offset"],
        limit=per_page,
    )
    context = Page.create(pag["page"], per_page, articles, total).as_context(
        "articles", search=q, category_slug=category, tag_slug=tag, status_filter=article_status
    )
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "kb/articles/partials/article_table.html", context)
    return templates.TemplateResponse(request, "kb/articles/list.html", context)


@router.get("/articles/new")
async def article_new(request: Request, db: DbDep, editor: KbEditor):
    return templates.TemplateResponse(
        request,
        "kb/articles/form.html",
        {
            "article": None,
            "categories": await kb_service.list_categories(db, include_counts=False),
            "tags": await kb_service.list_tags(db),
            "selected_tags": [],
        },
    )


@router.post("/articles")
async def article_create(request: Request, db: DbDep, editor: KbEditor):
    form = await request.form()
    title = str(form.get("title", "")).strip()
    if not title:
        raise BadRequestError(detail="Title is required")
    publish = str(form.get("action", "draft")) == "publish"
    article = await kb_service.create_article(
        db,
        editor,
        title=title,
        summary=str(form.get("summary", "")).strip(),
        body=str(form.get("body", "")),
        category_id=_parse_uuid(form.get("category_id")),
        visibility=_parse_visibility(form.get("visibility")),
        status=KbArticleStatus.PUBLISHED if publish else KbArticleStatus.DRAFT,
    )
    tag_names = _parse_tags(form.get("tags"))
    if tag_names:
        await kb_service.set_article_tags(db, editor, article, tag_names)
    return RedirectResponse(f"/kb/articles/{article.slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/articles/{slug}/edit")
async def article_edit(request: Request, db: DbDep, editor: KbEditor, slug: str):
    article = await kb_service.get_article_by_slug(db, slug, editor)
    return templates.TemplateResponse(
        request,
        "kb/articles/form.html",
        {
            "article": article,
            "categories": await kb_service.list_categories(db, include_counts=False),
            "tags": await kb_service.list_tags(db),
            "selected_tags": [tag.name for tag in article.tags],
        },
    )


@router.get("/articles/{slug}/history")
async def article_history(request: Request, db: DbDep, editor: KbEditor, slug: str):
    article = await kb_service.get_article_by_slug(db, slug, editor)
    return templates.TemplateResponse(
        request, "kb/articles/partials/revision_list.html", {"article": article, "revisions": await kb_service.list_revisions(db, article)}
    )


@router.post("/articles/{slug}/attachments")
async def upload_attachment(request: Request, db: DbDep, editor: KbEditor, slug: str):
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise BadRequestError(detail="No file provided")
    article = await kb_service.get_article_by_slug(db, slug, editor)
    await kb_service.add_attachment(db, editor, article, upload)
    return RedirectResponse(f"/kb/articles/{article.slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/articles/{slug}/attachments/{attachment_id}/delete")
async def remove_attachment(request: Request, db: DbDep, editor: KbEditor, slug: str, attachment_id: uuid.UUID):
    article = await kb_service.get_article_by_slug(db, slug, editor)
    attachment = await kb_service.get_attachment(db, article, attachment_id)
    await kb_service.delete_attachment(db, editor, article, attachment)
    return RedirectResponse(f"/kb/articles/{article.slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/articles/{slug}/feedback")
async def article_feedback(request: Request, db: DbDep, user: CurrentUser, slug: str):
    article = await kb_service.get_article_by_slug(db, slug, user)
    form = await request.form()
    is_helpful = str(form.get("is_helpful", "1")) == "1"
    comment = str(form.get("comment", "")).strip() or None
    await kb_service.submit_feedback(db, user, article, is_helpful=is_helpful, comment=comment)
    return templates.TemplateResponse(
        request,
        "kb/articles/partials/feedback.html",
        {
            "article": article,
            "feedback": await kb_service.feedback_summary(db, article.id),
            "my_feedback": await kb_service.get_user_feedback(db, article.id, user.id),
        },
    )


@router.post("/articles/{slug}/status")
async def article_status(request: Request, db: DbDep, editor: KbEditor, slug: str):
    form = await request.form()
    target = _parse_status(form.get("status"))
    if target is None:
        raise BadRequestError(detail="Invalid status")
    article = await kb_service.get_article_by_slug(db, slug, editor)
    await kb_service.set_status(db, editor, article, target)
    return RedirectResponse(f"/kb/articles/{article.slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/articles/{slug}/restore/{revision_id}")
async def article_restore(request: Request, db: DbDep, editor: KbEditor, slug: str, revision_id: uuid.UUID):
    article = await kb_service.get_article_by_slug(db, slug, editor)
    revision = await kb_service.get_revision(db, article, revision_id)
    await kb_service.restore_revision(db, editor, article, revision)
    return RedirectResponse(f"/kb/articles/{article.slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/articles/{slug}")
async def article_update(request: Request, db: DbDep, editor: KbEditor, slug: str):
    form = await request.form()
    title = str(form.get("title", "")).strip()
    if not title:
        raise BadRequestError(detail="Title is required")
    article = await kb_service.get_article_by_slug(db, slug, editor)
    await kb_service.update_article(
        db,
        editor,
        article,
        title=title,
        summary=str(form.get("summary", "")).strip(),
        body=str(form.get("body", "")),
        category_id=_parse_uuid(form.get("category_id")),
        visibility=_parse_visibility(form.get("visibility")),
    )
    await kb_service.set_article_tags(db, editor, article, _parse_tags(form.get("tags")))
    return RedirectResponse(f"/kb/articles/{article.slug}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/articles/{slug}")
async def article_detail(request: Request, db: DbDep, user: OptionalUser, slug: str):
    article = await kb_service.get_article_by_slug(db, slug, user)
    await kb_service.increment_view(db, article, user)
    return templates.TemplateResponse(
        request,
        "kb/articles/detail.html",
        {
            "article": article,
            "body_html": markdown_utils.render_markdown(article.body),
            "feedback": await kb_service.feedback_summary(db, article.id),
            "my_feedback": await kb_service.get_user_feedback(db, article.id, user.id) if user else None,
            "can_edit": kb_service.is_editor(user),
        },
    )


# --------------------------------------------------------------------------- #
# Tags
# --------------------------------------------------------------------------- #
@router.get("/tags")
async def tags_page(request: Request, db: DbDep, editor: KbEditor):
    return templates.TemplateResponse(request, "kb/tags/list.html", {"tags": await kb_service.list_tags(db)})


@router.post("/tags/{tag_id}/delete")
async def tag_delete(request: Request, db: DbDep, editor: KbEditor, tag_id: uuid.UUID):
    tag = await kb_service.get_tag_by_id(db, tag_id)
    await kb_service.delete_tag(db, editor, tag)
    return RedirectResponse("/kb/tags", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/tags/{slug}")
async def tag_articles(request: Request, db: DbDep, user: OptionalUser, slug: str, page: int = 1):
    tag = await kb_service.get_tag_by_slug(db, slug)
    per_page = clamp_per_page(PAGE_SIZE)
    total = await kb_service.count_articles(db, user, tag_id=tag.id)
    pag = paginate(page, per_page, total)
    articles = await kb_service.list_articles(db, user, tag_id=tag.id, offset=pag["offset"], limit=per_page)
    context = Page.create(pag["page"], per_page, articles, total).as_context("articles", heading=f"#{tag.name}", tag=tag)
    return templates.TemplateResponse(request, "kb/articles/list.html", context)


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
@router.get("/search")
async def search(
    request: Request,
    db: DbDep,
    user: OptionalUser,
    q: str = "",
    category: str = "",
    tag: str = "",
    page: int = 1,
):
    per_page = clamp_per_page(PAGE_SIZE)
    query = q.strip()
    results: list = []
    total = 0
    if len(query) >= 2:
        tag_ids = [tid for tid in [await _filter_tag_id(db, tag)] if tid]
        category_id = await _filter_category_id(db, category)
        total = await kb_service.count_search_articles(db, user, query, category_id=category_id, tag_ids=tag_ids)
        pag = paginate(page, per_page, total)
        results = await kb_service.search_articles(
            db,
            user,
            query,
            category_id=category_id,
            tag_ids=tag_ids,
            offset=pag["offset"],
            limit=per_page,
        )
    else:
        pag = paginate(page, per_page, total)
    context = Page.create(pag["page"], per_page, results, total).as_context("articles", search=q, category_slug=category, tag_slug=tag)
    context["categories"] = await kb_service.list_categories(db, include_counts=False)
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "kb/partials/result_list.html", context)
    return templates.TemplateResponse(request, "kb/search.html", context)


@router.get("/partials/search")
async def search_partial(request: Request, db: DbDep, user: OptionalUser, q: str = ""):
    query = q.strip()
    results: list = []
    total = 0
    if len(query) >= 2:
        results = await kb_service.search_articles(db, user, query, offset=0, limit=5)
        total = await kb_service.count_search_articles(db, user, query)
    return templates.TemplateResponse(request, "kb/partials/result_list.html", {"articles": results, "search": q, "total": total})
