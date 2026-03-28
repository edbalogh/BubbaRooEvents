from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.monitoring import MetricsMiddleware, init_sentry, metrics
from app.integrations.slack_bot import router as slack_router

# Initialize Sentry if configured
init_sentry(
    dsn=getattr(settings, "sentry_dsn", ""),
    environment=settings.app_env,
)

app = FastAPI(
    title="BubbaRoo Events",
    description="Local events discovery and recommendation platform",
    version="0.1.0",
)

app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(slack_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "env": settings.app_env}


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    return metrics.get_metrics_text()
