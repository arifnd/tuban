from fastapi import APIRouter, Request

from src.auth.dependencies import CurrentUser, DbDep
from src.search import service as search_service
from src.search.schemas import SearchResults
from src.templating import templates

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search_page(request: Request, db: DbDep, user: CurrentUser, q: str = "", type: str = ""):
    results = await search_service.search(db, user, q)
    if type == "kb":
        results["hits"] = results["kb"]
    elif type == "ticket":
        results["hits"] = results["tickets"]
    results["type_filter"] = type
    return templates.TemplateResponse(request, "search/results.html", results)


@router.get("/partials/dropdown")
async def search_dropdown(request: Request, db: DbDep, user: CurrentUser, q: str = ""):
    return templates.TemplateResponse(request, "partials/search_dropdown.html", await search_service.search(db, user, q, limit=8))


@router.get("/api", response_model=SearchResults)
async def search_api(db: DbDep, user: CurrentUser, q: str = "") -> SearchResults:
    return SearchResults(**await search_service.search(db, user, q))
