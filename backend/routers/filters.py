from fastapi import APIRouter
from services import pg_service

router = APIRouter(prefix="/api/filters", tags=["filters"])


@router.get("/options")
def filter_options():
    return pg_service.get_filter_options()
