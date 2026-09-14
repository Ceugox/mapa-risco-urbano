import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import analytics
from .collectors.base import run_collector
from .collectors.cemaden import collect as collect_cemaden
from .collectors.cge import collect as collect_cge
from .collectors.inmet import collect as collect_inmet
from .collectors.meteo import collect as collect_meteo
from .config import settings
from .db import get_reports, init_db, store_snapshot
from .routers.admin import router as admin_router
from .routers.auth import router as auth_router
from .routers.ingest import router as ingest_router
from .routers.layers import router as layers_router
from .routers.reports import router as reports_router
from .routers.route import router as route_router
from .routers.support import router as support_router
from .routers.whatsapp import router as whatsapp_router


def _reports_payload():
    reports = get_reports()
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "id": r["id"],
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {k: r[k] for k in ("id", "category", "description", "created_at", "expires_at", "confirmations", "status", "source")},
        } for r in reports],
    }


def _crime_payload():
    path = Path(__file__).resolve().parents[1] / "data" / "crime_h3.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"type": "FeatureCollection", "features": []}


async def collect_all():
    await asyncio.gather(
        asyncio.to_thread(run_collector, "alagamento", collect_cge),
        asyncio.to_thread(run_collector, "cemaden", collect_cemaden),
        asyncio.to_thread(run_collector, "inmet", collect_inmet),
        asyncio.to_thread(run_collector, "clima", collect_meteo),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    store_snapshot("crime", _crime_payload())
    store_snapshot("reports", _reports_payload())
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(asyncio.to_thread(run_collector, "alagamento", collect_cge)), "interval", seconds=settings.cge_interval, id="cge", max_instances=1)
    scheduler.add_job(lambda: asyncio.create_task(asyncio.to_thread(run_collector, "cemaden", collect_cemaden)), "interval", seconds=settings.cemaden_interval, id="cemaden", max_instances=1)
    scheduler.add_job(lambda: asyncio.create_task(asyncio.to_thread(run_collector, "inmet", collect_inmet)), "interval", seconds=settings.inmet_interval, id="inmet", max_instances=1)
    scheduler.add_job(lambda: asyncio.create_task(asyncio.to_thread(run_collector, "clima", collect_meteo)), "interval", seconds=settings.meteo_interval, id="meteo", max_instances=1)
    scheduler.add_job(lambda: asyncio.create_task(asyncio.to_thread(analytics.flush)), "interval", seconds=15, id="analytics_flush", max_instances=1)
    scheduler.add_job(lambda: asyncio.create_task(asyncio.to_thread(analytics.purge, settings.analytics_retention_days)), "interval", hours=6, id="analytics_purge", max_instances=1)
    scheduler.start()
    asyncio.create_task(collect_all())
    yield
    scheduler.shutdown(wait=False)
    await asyncio.to_thread(analytics.flush)


app = FastAPI(title="MapaSP", lifespan=lifespan)
app.add_middleware(analytics.AccessLogMiddleware)
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(layers_router)
app.include_router(reports_router)
app.include_router(ingest_router)
app.include_router(whatsapp_router)
app.include_router(route_router)
app.include_router(support_router)


@app.get("/health")
def health():
    return {"ok": True}


DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():

    @app.get("/admin", include_in_schema=False)
    def admin_page():
        return FileResponse(DIST / "index.html")

    app.mount("/", StaticFiles(directory=DIST, html=True), name="site")
else:

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("http://localhost:5173")
