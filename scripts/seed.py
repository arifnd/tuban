"""Seed the database with demo data.

Usage::

    python -m scripts.seed            # add demo data
    python -m scripts.seed --reset    # wipe everything first
"""

import argparse
import asyncio

from sqlalchemy import delete

from src.activity.models import ActivityLog
from src.auth import service as auth_service
from src.database import SessionFactory
from src.kb import service as kb_service
from src.kb.models import KbArticle, KbArticleFeedback, KbArticleRevision, KbArticleStatus, KbArticleTag, KbArticleVisibility, KbAttachment, KbCategory, KbTag
from src.notifications.models import Notification
from src.settings import service as settings_service
from src.tickets import service as ticket_service
from src.tickets.models import Ticket, TicketAttachment, TicketCategory, TicketComment, TicketNumberSeq, TicketPriority, TicketStatus
from src.users.models import User, UserRole

USERS = [
    ("admin@example.com", UserRole.ADMIN, "Site Admin"),
    ("ada@example.com", UserRole.AGENT, "Ada Agent"),
    ("grace@example.com", UserRole.AGENT, "Grace Agent"),
    ("user@example.com", UserRole.USER, "Uma User"),
    ("bob@example.com", UserRole.USER, "Bob Requester"),
]

ARTICLES = [
    ("Getting started", "How to sign in and find your way around.", "Welcome! Use the top navigation to reach the knowledge base and tickets."),
    ("Refund policy", "When and how refunds are issued.", "Refunds are available within **30 days**. Open a ticket with your order number."),
    ("Resetting your password", "Steps to regain access.", "Use the password reset link. If it fails, open a ticket."),
    ("Printer troubleshooting", "Common printer fixes.", "- Check cables\n- Restart the printer\n- Reinstall the driver"),
]

# (title, summary, body, visibility, status)
EXTRA_ARTICLES = [
    (
        "Internal escalation runbook",
        "Agent-only steps for escalating incidents.",
        "This runbook is for agents only and must not appear on the public landing page.",
        KbArticleVisibility.INTERNAL,
        KbArticleStatus.PUBLISHED,
    ),
    (
        "Upcoming billing changes (draft)",
        "Draft notes pending review.",
        "This draft is not published yet.",
        KbArticleVisibility.PUBLIC,
        KbArticleStatus.DRAFT,
    ),
]

SETTINGS = {
    "contact_email": "support@example.com",
    "contact_phone": "+62 21 555 0100",
    "contact_address": "Jl. Merdeka No. 1, Jakarta",
    "social_facebook": "https://facebook.com/batikhelpdesk",
    "social_instagram": "https://instagram.com/batikhelpdesk",
    "social_x": "https://x.com/batikhelpdesk",
    "social_linkedin": "https://linkedin.com/company/batikhelpdesk",
    "social_youtube": "https://youtube.com/@batikhelpdesk",
    "carousel_image_1": "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1600&q=80",
    "carousel_image_2": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=1600&q=80",
    "carousel_image_3": "https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=1600&q=80",
}


async def _reset(db) -> None:
    for model in (
        ActivityLog,
        Notification,
        TicketComment,
        TicketAttachment,
        Ticket,
        TicketCategory,
        TicketNumberSeq,
        KbArticleFeedback,
        KbAttachment,
        KbArticleRevision,
        KbArticleTag,
        KbArticle,
        KbTag,
        KbCategory,
        User,
    ):
        await db.execute(delete(model))
    await db.commit()


async def _user(db, email: str, role: UserRole, name: str) -> User:
    user = await auth_service.dev_login(db, email)
    user.role = role
    user.name = name
    await db.commit()
    await db.refresh(user)
    return user


async def seed() -> None:
    async with SessionFactory() as db:
        users = {email: await _user(db, email, role, name) for email, role, name in USERS}
        admin, ada, grace, uma, bob = (
            users["admin@example.com"],
            users["ada@example.com"],
            users["grace@example.com"],
            users["user@example.com"],
            users["bob@example.com"],
        )

        categories = {}
        for index, name in enumerate(("Getting Started", "Billing", "Troubleshooting")):
            categories[name] = await kb_service.create_category(db, admin, name=name, position=index)

        for title, summary, body in ARTICLES:
            category = categories["Billing" if "Refund" in title else "Troubleshooting" if "Printer" in title else "Getting Started"]
            article = await kb_service.create_article(
                db,
                admin,
                title=title,
                summary=summary,
                body=body,
                category_id=category.id,
                visibility=KbArticleVisibility.PUBLIC,
                status=KbArticleStatus.PUBLISHED,
            )
            await kb_service.set_article_tags(db, admin, article, ["basics", "how-to"])

        for title, summary, body, visibility, status in EXTRA_ARTICLES:
            await kb_service.create_article(
                db, admin, title=title, summary=summary, body=body, category_id=categories["Getting Started"].id, visibility=visibility, status=status
            )

        await settings_service.update(db, admin, SETTINGS)

        ticket_category = await ticket_service.create_category(db, admin, name="General")
        tickets = []
        for subject, description, priority in (
            ("Cannot sign in", "I keep getting an invalid password error.", TicketPriority.HIGH),
            ("Invoice question", "Where can I download last month's invoice?", TicketPriority.NORMAL),
            ("App crashes on launch", "The mobile app closes immediately.", TicketPriority.URGENT),
        ):
            tickets.append(
                await ticket_service.create_ticket(
                    db, bob if "Invoice" in subject else uma, subject=subject, description=description, category_id=ticket_category.id, priority=priority
                )
            )

        first = tickets[0]
        await ticket_service.assign_ticket(db, ada, first, ada)
        await ticket_service.add_comment(db, ada, first, "Thanks for reaching out — I can reproduce this.", is_internal=False)
        await ticket_service.add_comment(db, ada, first, "Checked the auth logs; token expiry looks wrong.", is_internal=True)
        await ticket_service.transition_status(db, ada, first, TicketStatus.RESOLVED)

        second = tickets[1]
        await ticket_service.assign_ticket(db, grace, second, grace)
        await ticket_service.add_comment(db, grace, second, "You can download it from Billing > Invoices.")

    print("Seed complete.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument("--reset", action="store_true", help="wipe existing data first")
    args = parser.parse_args()
    if args.reset:
        async with SessionFactory() as db:
            await _reset(db)
        print("Database reset.")
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
