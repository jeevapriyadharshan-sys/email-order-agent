from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .db import Base, engine
from .routes import auth, emails, orders, review, agent
from .config import settings
from .routes import settings as settings_route
from .routes import activity
from .worker import start_scheduler, stop_scheduler

# Create tables automatically
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: begin the APScheduler background tick
    start_scheduler()
    yield
    # Shutdown: stop the scheduler cleanly
    stop_scheduler()


app = FastAPI(title="Email Processing & Order Creation Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.APP_BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(emails.router)
app.include_router(review.router)
app.include_router(orders.router)
app.include_router(settings_route.router)
app.include_router(activity.router)


@app.get("/health")
def health():
    return {"ok": True}