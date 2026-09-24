import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_col


class KbArticleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KbArticleVisibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


class KbCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "kb_categories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    articles: Mapped[list["KbArticle"]] = relationship(back_populates="category")


class KbArticle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "kb_articles"
    __table_args__ = (Index("kb_articles_status_updated_idx", "status", "updated_at"),)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("kb_categories.id"), index=True, nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[KbArticleStatus] = mapped_column(enum_col(KbArticleStatus, "kb_article_status"), default=KbArticleStatus.DRAFT, nullable=False)
    visibility: Mapped[KbArticleVisibility] = mapped_column(
        enum_col(KbArticleVisibility, "kb_article_visibility"),
        default=KbArticleVisibility.INTERNAL,
        nullable=False,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped["KbCategory | None"] = relationship(back_populates="articles")
    revisions: Mapped[list["KbArticleRevision"]] = relationship(back_populates="article", cascade="all, delete-orphan")
    attachments: Mapped[list["KbAttachment"]] = relationship(back_populates="article", cascade="all, delete-orphan")
    feedback: Mapped[list["KbArticleFeedback"]] = relationship(back_populates="article", cascade="all, delete-orphan")
    tags: Mapped[list["KbTag"]] = relationship(secondary="kb_article_tags", back_populates="articles")


class KbArticleRevision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kb_article_revisions"
    __table_args__ = (UniqueConstraint("article_id", "revision_no", name="uq_kb_article_revisions_article_revision"),)

    article_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("kb_articles.id"), index=True, nullable=False)
    editor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    article: Mapped["KbArticle"] = relationship(back_populates="revisions")


class KbTag(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kb_tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    articles: Mapped[list["KbArticle"]] = relationship(secondary="kb_article_tags", back_populates="tags")


class KbArticleTag(Base):
    __tablename__ = "kb_article_tags"

    article_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("kb_articles.id"), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("kb_tags.id"), primary_key=True)


class KbAttachment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kb_attachments"

    article_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("kb_articles.id"), index=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    article: Mapped["KbArticle"] = relationship(back_populates="attachments")


class KbArticleFeedback(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "kb_article_feedback"
    __table_args__ = (UniqueConstraint("article_id", "user_id", name="uq_kb_article_feedback_article_user"),)

    article_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("kb_articles.id"), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    article: Mapped["KbArticle"] = relationship(back_populates="feedback")
