from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from openai import AsyncOpenAI

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


@app.get("/api/debug/dns")
async def debug_dns():
    """Temporary debug: dump MODEL_POOL raw + parsed values."""
    import os
    from app.config import get_settings

    s = get_settings()
    raw_env = os.environ.get("MODEL_POOL", "<not set>")
    pool = s.model_pool

    # Dump each provider's fields with repr to expose hidden chars
    providers_detail = []
    for i, p in enumerate(pool):
        providers_detail.append({
            "index": i,
            "key_repr": repr(p.get("key", "")),
            "key_len": len(p.get("key", "")),
            "base_url_repr": repr(p.get("base_url", "")),
            "base_url_len": len(p.get("base_url", "")),
            "model_repr": repr(p.get("model", "")),
            "model_len": len(p.get("model", "")),
        })

    return {
        "raw_env_repr": repr(raw_env),
        "raw_env_len": len(raw_env),
        "parsed_pool_len": len(pool),
        "providers": providers_detail,
        "OPENAI_API_KEY_set": bool(s.OPENAI_API_KEY),
        "OPENAI_BASE_URL_repr": repr(s.OPENAI_BASE_URL),
        "OPENAI_MODEL_repr": repr(s.OPENAI_MODEL),
    }
