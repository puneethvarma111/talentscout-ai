from app.config import get_settings
from app.database.repository import ResearchRepository


def get_repo() -> ResearchRepository:
    return ResearchRepository()


def get_settings_dep():
    return get_settings()
