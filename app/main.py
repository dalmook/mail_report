from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .db import init_db
from .logging_utils import configure_logging
from .routers.actions import build_router as build_action_router
from .routers.pages import build_router as build_page_router
from .scheduler import start_scheduler, stop_scheduler
from .services.summary_service import SummaryService

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    logger.info('Mail archive app started')
    yield
    stop_scheduler()
    logger.info('Mail archive app stopped')


app = FastAPI(title=settings.app_title, lifespan=lifespan)
app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))
summary_service = SummaryService()

app.include_router(build_page_router(templates))
app.include_router(build_action_router(summary_service))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception('Unhandled error: path=%s', request.url.path)
    return JSONResponse({'detail': '내부 오류가 발생했습니다. 로그를 확인하세요.'}, status_code=500)
