from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import init_db
from app.routers import projects, conversations, artifacts, executions, build

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title="Atoms Lite API",
    description="Project Driven AI Native Workspace",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - supports environment variable for production domains
origins_raw = settings.CORS_ORIGINS.strip()
if origins_raw == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(projects.router)
app.include_router(conversations.router)
app.include_router(artifacts.router)
app.include_router(executions.router)
app.include_router(build.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "atoms-lite-api"}
