import uvicorn
from fastapi import FastAPI
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.v1.router import router as api_router


settings = get_settings()
setup_logging(settings.LOG_LEVEL)


app = FastAPI(title=settings.APP_NAME, version="1.0.0")
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)
