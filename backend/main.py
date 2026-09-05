# backend/main.py
import logging
import threading
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from domains.tasks.router import router as tasks_router
from domains.health.router import router as health_router
from domains.knowledge.router import router as knowledge_router
from domains.journal.router import router as journal_router
from domains.finance.router import router as finance_router
from integrations.ha.router import router as ha_router
from integrations.calendar_router import router as calendar_router
from integrations.siri.router import router as siri_router
from integrations.health_auto_export_router import router as hae_router
from orchestrator.insights_router import router as insights_router
from orchestrator.chat_router import router as chat_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from scheduler import build_scheduler
    from bot.telegram import run_bot
    sched = build_scheduler()
    sched.start()
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    yield
    sched.shutdown()


app = FastAPI(title="Chitiyu PI", lifespan=lifespan)

app.include_router(tasks_router)
app.include_router(health_router)
app.include_router(knowledge_router)
app.include_router(journal_router)
app.include_router(finance_router)
app.include_router(ha_router)
app.include_router(calendar_router)
app.include_router(siri_router)
app.include_router(hae_router)
app.include_router(insights_router)
app.include_router(chat_router)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


_web_dist = Path(__file__).parent.parent / "app" / "dist"
if _web_dist.exists():
    app.mount("/assets", StaticFiles(directory=_web_dist / "assets"), name="assets")
    app.mount("/", StaticFiles(directory=_web_dist, html=True), name="web")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
