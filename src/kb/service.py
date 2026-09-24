import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity import service as activity_service
from src.kb.exceptions import (
    ArticleNotFound,
    CategoryHasArticles,
    InvalidStatusTransition,
    KbNotFound,
)
from src.kb.models import (
    KbArticle,
    KbArticleFeedback,
    KbArticleRevision,
    KbArticleStatus,
    KbArticleTag,
    KbArticleVisibility,
    KbAttachment,
    KbCategory,
    KbTag,
)
from src.kb.utils import normalize_tag, slugify
from src.storage import service as storage_service
from src.users.models import User, UserRole

EDITOR_ROLES = (UserRole.ADMIN, UserRole.AGENT)

STATUS_TRANSITIONS: dict[KbArticleStatus, set[KbArticleStatus]] = {
    KbArticleStatus.DRAFT: {KbArticleStatus.PUBLISHED},
    KbArticleStatus.PUBLISHED: {KbArticleStatus.ARCHIVED, KbArticleStatus.DRAFT},
    KbArticleStatus.ARCHIVED: {KbArticleStatus.PUBLISHED},
}


def is_editor(user: User | None) -> bool:
    return user is not None and user.role in EDITOR_ROLES


def _scope(stmt, viewer: User | None):
    if is_editor(viewer):
        return stmt
    return stmt.where(KbArticle.status == KbArticleStatus.PUBLISHED, KbArticle.visibility == KbArticleVisibility.PUBLIC)


async def _unique_slug(db: AsyncSession, model, base: str, exclude_id: uuid.UUID | None = None) -> str:
    root = slugify(base)
    candidate = root
    suffix = 1
    while True:
        stmt = select(model.id).where(model.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(model.id != exclude_id)
        if (await db.execute(stmt)).first() is None:
            return candidate
        suffix += 1
        candidate = f"{root}-{suffix}"


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
async def list_categories(db: AsyncSession, *, include_counts: bool = True, viewer: User | None = None) -> list[KbCategory]:
    categories = list((await db.execute(select(KbCategory).order_by(KbCategory.position, KbCategory.name))).scalars())
    if include_counts:
        count_stmt = select(KbArticle.category_id, func.count(KbArticle.id)).where(KbArticle.status == KbArticleStatus.PUBLISHED)
        if not is_editor(viewer):
            count_stmt = count_stmt.where(KbArticle.visibility == KbArticleVisibility.PUBLIC)
        rows = (await db.execute(count_stmt.group_by(KbArticle.category_id))).all()
        counts = {category_id: count for category_id, count in rows}
        for category in categories:
            category.article_count = counts.get(category.id, 0)
    return categories


async def get_category_by_id(db: AsyncSession, category_id: uuid.UUID) -> KbCategory:
    category = await db.get(KbCategory, category_id)
    if category is None:
        raise KbNotFound(detail="Category not found")
    return category


async def get_category_by_slug(db: AsyncSession, slug: str) -> KbCategory:
    category = (await db.execute(select(KbCategory).where(KbCategory.slug == slug))).scalar_one_or_none()
    if category is None:
        raise KbNotFound(detail="Category not found")
    return category


async def create_category(db: AsyncSession, actor: User, *, name: str, description: str | None = None, position: int = 0) -> KbCategory:
    category = KbCategory(name=name.strip(), slug=await _unique_slug(db, KbCategory, name), description=description or None, position=position)
    db.add(category)
    await db.flush()
    await activity_service.log(db, user_id=actor.id, action="create", entity_type="kb_categories", entity_id=category.id, new_data={"name": category.name})
    await db.commit()
    await db.refresh(category)
    category.article_count = 0
    return category


async def update_category(db: AsyncSession, actor: User, category: KbCategory, *, name: str, description: str | None, position: int) -> KbCategory:
    old = {"name": category.name, "position": category.position}
    if name.strip() != category.name:
        category.name = name.strip()
        category.slug = await _unique_slug(db, KbCategory, name, exclude_id=category.id)
    category.description = description or None
    category.position = position
    await activity_service.log(
        db,
        user_id=actor.id,
        action="update",
        entity_type="kb_categories",
        entity_id=category.id,
        old_data=old,
        new_data={"name": category.name, "position": position},
    )
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, actor: User, category: KbCategory) -> None:
    count = (await db.scalar(select(func.count()).select_from(KbArticle).where(KbArticle.category_id == category.id))) or 0
    if count:
        raise CategoryHasArticles()
    await activity_service.log(db, user_id=actor.id, action="delete", entity_type="kb_categories", entity_id=category.id, old_data={"name": category.name})
    await db.delete(category)
    await db.commit()


async def reorder_categories(db: AsyncSession, actor: User, ordered_ids: list[uuid.UUID]) -> None:
    for index, category_id in enumerate(ordered_ids):
        await db.execute(update(KbCategory).where(KbCategory.id == category_id).values(position=index).execution_options(synchronize_session=False))
    await activity_service.log(db, user_id=actor.id, action="update", entity_type="kb_categories", new_data={"order": [str(i) for i in ordered_ids]})
    await db.commit()


# --------------------------------------------------------------------------- #
# Articles
# --------------------------------------------------------------------------- #
async def list_articles(
    db: AsyncSession,
    viewer: User | None,
    *,
    q: str | None = None,
    category_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    status: KbArticleStatus | None = None,
    visibility: KbArticleVisibility | None = None,
    author_id: uuid.UUID | None = None,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[KbArticle], int]:
    stmt = _scope(select(KbArticle), viewer)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(KbArticle.title.ilike(like), KbArticle.summary.ilike(like), KbArticle.body.ilike(like)))
    if category_id is not None:
        stmt = stmt.where(KbArticle.category_id == category_id)
    if tag_id is not None:
        stmt = stmt.join(KbArticleTag, KbArticleTag.article_id == KbArticle.id).where(KbArticleTag.tag_id == tag_id)
    if status is not None and is_editor(viewer):
        stmt = stmt.where(KbArticle.status == status)
    if visibility is not None and is_editor(viewer):
        stmt = stmt.where(KbArticle.visibility == visibility)
    if author_id is not None:
        stmt = stmt.where(KbArticle.author_id == author_id)
    total = (await db.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
    rows = (await db.execute(stmt.order_by(KbArticle.updated_at.desc()).offset((page - 1) * per_page).limit(per_page))).scalars().all()
    return list(rows), total


async def recent_articles(db: AsyncSession, viewer: User | None, limit: int = 5) -> list[KbArticle]:
    stmt = _scope(select(KbArticle), viewer).order_by(KbArticle.published_at.desc().nullslast(), KbArticle.updated_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars())


async def popular_articles(db: AsyncSession, viewer: User | None, limit: int = 5) -> list[KbArticle]:
    stmt = _scope(select(KbArticle), viewer).order_by(KbArticle.view_count.desc(), KbArticle.updated_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars())


async def get_article_by_slug(db: AsyncSession, slug: str, viewer: User | None) -> KbArticle:
    article = (await db.execute(_scope(select(KbArticle), viewer).where(KbArticle.slug == slug))).scalar_one_or_none()
    if article is None:
        raise ArticleNotFound()
    return article


async def get_article_by_id(db: AsyncSession, article_id: uuid.UUID, viewer: User | None) -> KbArticle | None:
    return (await db.execute(_scope(select(KbArticle), viewer).where(KbArticle.id == article_id))).scalar_one_or_none()


async def create_article(
    db: AsyncSession,
    actor: User,
    *,
    title: str,
    summary: str | None = None,
    body: str = "",
    category_id: uuid.UUID | None = None,
    visibility: KbArticleVisibility = KbArticleVisibility.INTERNAL,
    status: KbArticleStatus = KbArticleStatus.DRAFT,
) -> KbArticle:
    article = KbArticle(
        title=title.strip(),
        slug=await _unique_slug(db, KbArticle, title),
        summary=summary or None,
        body=body or "",
        category_id=category_id,
        author_id=actor.id,
        status=status,
        visibility=visibility,
        published_at=datetime.now(UTC) if status == KbArticleStatus.PUBLISHED else None,
    )
    db.add(article)
    await db.flush()
    db.add(KbArticleRevision(article_id=article.id, editor_id=actor.id, title=article.title, body=article.body, revision_no=1))
    await activity_service.log(
        db, user_id=actor.id, action="create", entity_type="kb_articles", entity_id=article.id, new_data={"title": article.title, "status": status.value}
    )
    await db.commit()
    await db.refresh(article)
    return article


async def _next_revision_no(db: AsyncSession, article_id: uuid.UUID) -> int:
    current = await db.scalar(select(func.max(KbArticleRevision.revision_no)).where(KbArticleRevision.article_id == article_id))
    return (current or 0) + 1


async def update_article(
    db: AsyncSession,
    actor: User,
    article: KbArticle,
    *,
    title: str,
    summary: str | None,
    body: str,
    category_id: uuid.UUID | None,
    visibility: KbArticleVisibility,
) -> KbArticle:
    content_changed = title.strip() != article.title or (body or "") != article.body
    old = {"title": article.title, "visibility": article.visibility.value}
    if title.strip() != article.title:
        article.title = title.strip()
        article.slug = await _unique_slug(db, KbArticle, article.title, exclude_id=article.id)
    article.summary = summary or None
    article.body = body or ""
    article.category_id = category_id
    article.visibility = visibility
    if content_changed:
        db.add(
            KbArticleRevision(
                article_id=article.id, editor_id=actor.id, title=article.title, body=article.body, revision_no=await _next_revision_no(db, article.id)
            )
        )
    await activity_service.log(
        db,
        user_id=actor.id,
        action="update",
        entity_type="kb_articles",
        entity_id=article.id,
        old_data=old,
        new_data={"title": article.title, "visibility": visibility.value},
    )
    await db.commit()
    await db.refresh(article)
    return article


async def set_status(db: AsyncSession, actor: User, article: KbArticle, status: KbArticleStatus) -> KbArticle:
    if status != article.status and status not in STATUS_TRANSITIONS.get(article.status, set()):
        raise InvalidStatusTransition(detail=f"Cannot move from {article.status.value} to {status.value}")
    old = article.status.value
    article.status = status
    if status == KbArticleStatus.PUBLISHED and article.published_at is None:
        article.published_at = datetime.now(UTC)
    await activity_service.log(
        db, user_id=actor.id, action=status.value, entity_type="kb_articles", entity_id=article.id, old_data={"status": old}, new_data={"status": status.value}
    )
    await db.commit()
    await db.refresh(article)
    return article


async def list_revisions(db: AsyncSession, article: KbArticle) -> list[KbArticleRevision]:
    stmt = select(KbArticleRevision).where(KbArticleRevision.article_id == article.id).order_by(KbArticleRevision.revision_no.desc())
    return list((await db.execute(stmt)).scalars())


async def get_revision(db: AsyncSession, article: KbArticle, revision_id: uuid.UUID) -> KbArticleRevision:
    revision = (
        await db.execute(select(KbArticleRevision).where(KbArticleRevision.id == revision_id, KbArticleRevision.article_id == article.id))
    ).scalar_one_or_none()
    if revision is None:
        raise KbNotFound(detail="Revision not found")
    return revision


async def restore_revision(db: AsyncSession, actor: User, article: KbArticle, revision: KbArticleRevision) -> KbArticle:
    article.title = revision.title
    article.body = revision.body
    article.slug = await _unique_slug(db, KbArticle, revision.title, exclude_id=article.id)
    db.add(
        KbArticleRevision(
            article_id=article.id, editor_id=actor.id, title=article.title, body=article.body, revision_no=await _next_revision_no(db, article.id)
        )
    )
    await activity_service.log(
        db, user_id=actor.id, action="restore", entity_type="kb_articles", entity_id=article.id, new_data={"revision_no": revision.revision_no}
    )
    await db.commit()
    await db.refresh(article)
    return article


async def increment_view(db: AsyncSession, article: KbArticle, viewer: User | None) -> None:
    if viewer is not None and viewer.id == article.author_id:
        return
    await db.execute(
        update(KbArticle).where(KbArticle.id == article.id).values(view_count=KbArticle.view_count + 1).execution_options(synchronize_session=False)
    )
    await db.commit()
    await db.refresh(article)


# --------------------------------------------------------------------------- #
# Tags
# --------------------------------------------------------------------------- #
async def list_tags(db: AsyncSession, q: str | None = None) -> list[KbTag]:
    stmt = select(KbTag).order_by(KbTag.name)
    if q:
        stmt = stmt.where(KbTag.name.ilike(f"%{q}%"))
    tags = list((await db.execute(stmt)).scalars())
    rows = (await db.execute(select(KbArticleTag.tag_id, func.count(KbArticleTag.article_id)).group_by(KbArticleTag.tag_id))).all()
    counts = {tag_id: count for tag_id, count in rows}
    for tag in tags:
        tag.article_count = counts.get(tag.id, 0)
    return tags


async def get_tag_by_slug(db: AsyncSession, slug: str) -> KbTag:
    tag = (await db.execute(select(KbTag).where(KbTag.slug == slug))).scalar_one_or_none()
    if tag is None:
        raise KbNotFound(detail="Tag not found")
    return tag


async def get_tag_by_id(db: AsyncSession, tag_id: uuid.UUID) -> KbTag:
    tag = await db.get(KbTag, tag_id)
    if tag is None:
        raise KbNotFound(detail="Tag not found")
    return tag


async def get_or_create_tags(db: AsyncSession, names: list[str]) -> list[KbTag]:
    tags: list[KbTag] = []
    seen: set[str] = set()
    for raw in names:
        name = normalize_tag(raw)
        if not name:
            continue
        slug = slugify(name)
        if slug in seen:
            continue
        seen.add(slug)
        tag = (await db.execute(select(KbTag).where(KbTag.slug == slug))).scalar_one_or_none()
        if tag is None:
            tag = KbTag(name=name, slug=slug)
            db.add(tag)
            await db.flush()
        tags.append(tag)
    return tags


async def set_article_tags(db: AsyncSession, actor: User, article: KbArticle, names: list[str]) -> KbArticle:
    tags = await get_or_create_tags(db, names)
    article.tags = tags
    await activity_service.log(
        db, user_id=actor.id, action="update", entity_type="kb_articles", entity_id=article.id, new_data={"tags": [tag.name for tag in tags]}
    )
    await db.commit()
    await db.refresh(article)
    return article


async def delete_tag(db: AsyncSession, actor: User, tag: KbTag) -> None:
    await activity_service.log(db, user_id=actor.id, action="delete", entity_type="kb_tags", entity_id=tag.id, old_data={"name": tag.name})
    await db.delete(tag)
    await db.commit()


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
async def search_articles(
    db: AsyncSession,
    viewer: User | None,
    q: str,
    *,
    category_id: uuid.UUID | None = None,
    tag_ids: list[uuid.UUID] | None = None,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[KbArticle], int]:
    like = f"%{q}%"
    rank = case(
        (KbArticle.title.ilike(like), 3),
        (KbArticle.summary.ilike(like), 2),
        (KbArticle.body.ilike(like), 1),
        else_=0,
    )
    stmt = _scope(select(KbArticle), viewer).where(or_(KbArticle.title.ilike(like), KbArticle.summary.ilike(like), KbArticle.body.ilike(like)))
    if category_id is not None:
        stmt = stmt.where(KbArticle.category_id == category_id)
    if tag_ids:
        tagged = select(KbArticleTag.article_id).where(KbArticleTag.tag_id.in_(tag_ids))
        stmt = stmt.where(KbArticle.id.in_(tagged))
    total = (await db.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
    rows = (await db.execute(stmt.order_by(rank.desc(), KbArticle.updated_at.desc()).offset((page - 1) * per_page).limit(per_page))).scalars().all()
    return list(rows), total


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #
async def submit_feedback(db: AsyncSession, user: User, article: KbArticle, *, is_helpful: bool, comment: str | None = None) -> KbArticleFeedback:
    existing = (
        await db.execute(select(KbArticleFeedback).where(KbArticleFeedback.article_id == article.id, KbArticleFeedback.user_id == user.id))
    ).scalar_one_or_none()
    if existing is None:
        existing = KbArticleFeedback(article_id=article.id, user_id=user.id, is_helpful=is_helpful, comment=comment or None)
        db.add(existing)
    else:
        existing.is_helpful = is_helpful
        existing.comment = comment or None
    await db.commit()
    await db.refresh(existing)
    return existing


def feedback_stats(article: KbArticle) -> dict:
    entries = article.feedback or []
    helpful = sum(1 for entry in entries if entry.is_helpful)
    return {"helpful": helpful, "total": len(entries)}


async def feedback_summary(db: AsyncSession, article_id: uuid.UUID) -> dict:
    row = (
        await db.execute(
            select(
                func.count(KbArticleFeedback.id),
                func.count(KbArticleFeedback.id).filter(KbArticleFeedback.is_helpful.is_(True)),
            ).where(KbArticleFeedback.article_id == article_id)
        )
    ).one()
    return {"total": row[0], "helpful": row[1]}


async def get_user_feedback(db: AsyncSession, article_id: uuid.UUID, user_id: uuid.UUID) -> KbArticleFeedback | None:
    return (
        await db.execute(select(KbArticleFeedback).where(KbArticleFeedback.article_id == article_id, KbArticleFeedback.user_id == user_id))
    ).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Attachments
# --------------------------------------------------------------------------- #
async def add_attachment(db: AsyncSession, actor: User, article: KbArticle, upload: UploadFile) -> KbAttachment:
    key, filename, size = await storage_service.save_upload(upload, prefix=f"kb/{article.id}")
    attachment = KbAttachment(
        article_id=article.id,
        file_name=filename,
        file_path=key,
        mime_type=upload.content_type,
        size_bytes=size,
        uploaded_by=actor.id,
    )
    db.add(attachment)
    await activity_service.log(db, user_id=actor.id, action="create", entity_type="kb_attachments", entity_id=article.id, new_data={"file_name": filename})
    await db.commit()
    await db.refresh(attachment)
    await db.refresh(article)
    return attachment


async def get_attachment(db: AsyncSession, article: KbArticle, attachment_id: uuid.UUID) -> KbAttachment:
    attachment = (await db.execute(select(KbAttachment).where(KbAttachment.id == attachment_id, KbAttachment.article_id == article.id))).scalar_one_or_none()
    if attachment is None:
        raise KbNotFound(detail="Attachment not found")
    return attachment


async def delete_attachment(db: AsyncSession, actor: User, article: KbArticle, attachment: KbAttachment) -> None:
    await storage_service.delete_upload(attachment.file_path)
    await activity_service.log(
        db, user_id=actor.id, action="delete", entity_type="kb_attachments", entity_id=article.id, old_data={"file_name": attachment.file_name}
    )
    await db.delete(attachment)
    await db.commit()
    await db.refresh(article)


__all__ = [
    "add_attachment",
    "create_article",
    "create_category",
    "delete_attachment",
    "delete_category",
    "delete_tag",
    "feedback_stats",
    "feedback_summary",
    "get_user_feedback",
    "get_article_by_id",
    "get_article_by_slug",
    "get_attachment",
    "get_category_by_id",
    "get_category_by_slug",
    "get_or_create_tags",
    "get_revision",
    "get_tag_by_id",
    "get_tag_by_slug",
    "increment_view",
    "is_editor",
    "list_articles",
    "list_categories",
    "list_revisions",
    "list_tags",
    "popular_articles",
    "recent_articles",
    "reorder_categories",
    "restore_revision",
    "search_articles",
    "set_article_tags",
    "set_status",
    "submit_feedback",
    "update_article",
    "update_category",
]
