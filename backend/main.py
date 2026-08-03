# backend/main.py
import logging
import threading
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from domains.tasks.router import router as tasks_router
from domains.health.router import router as health_router
from domains.knowledge.router import router as knowledge_router
from domains.journal.router import router as journal_router
from integrations.ha.router import router as ha_router

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
app.include_router(ha_router)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
