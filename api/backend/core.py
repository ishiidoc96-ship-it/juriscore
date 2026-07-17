from api.backend.models.database import async_session


async def get_session():
    """Dependency that yields an async database session."""
    async with async_session() as session:
        yield session
