import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import engine, Base, get_db
from backend.seed_data import seed_sample_workspace
from backend.routes import brands, rules, content, reviews, workflow, audit, dashboard, insights
from backend.routes import auth_routes, creatives, sources, intel
from backend import models_r3  # noqa: F401  (registers Round 3 tables)
from backend.migrations import run_migrations

# Ensure tables exist immediately, then apply additive column migrations.
Base.metadata.create_all(bind=engine)
try:
    run_migrations(engine)
except Exception:
    # A concurrent cold start applied the same step first; the next start re-checks.
    pass

# Serverless runtimes (Vercel) may not run the lifespan hook, so seed at import there too.
if os.getenv("VERCEL"):
    _db = next(get_db())
    try:
        seed_sample_workspace(_db, force_reset=False)
    except Exception:
        # Another instance seeded the shared database at the same moment (unique slug).
        _db.rollback()
    finally:
        _db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables and sample workspace exists on first run
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        seed_sample_workspace(db, force_reset=False)
    finally:
        db.close()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AUDITRA — AI-Powered Brand Governance & Content Review Platform",
    lifespan=lifespan
)

# The SPA is served from the same origin, so cross-origin access is off unless explicitly configured.
_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if _cors:
    app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-Auditra-Client"])


@app.middleware("http")
async def csrf_and_headers(request: Request, call_next):
    # State-changing API calls must carry a custom header. Browsers cannot add it cross-site
    # without a CORS preflight, which blocks cookie-riding form posts (defence in depth with SameSite=Lax).
    if request.url.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.headers.get("x-auditra-client") != "web":
            return JSONResponse({"detail": "Missing X-Auditra-Client header."}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response

# Health endpoint
@app.get("/api/health")
def health_check():
    ai_status = "configured" if (settings.GEMINI_API_KEY or settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY) else "deterministic_fallback"
    return {
        "status": "healthy",
        "service": "AUDITRA Governance API",
        "version": settings.VERSION,
        "ai_engine": ai_status,
        "database": "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql",
        "commit": os.getenv("VERCEL_GIT_COMMIT_SHA", "local")[:7],
    }

# Register API Routers
app.include_router(brands.router, prefix=settings.API_V1_STR)
app.include_router(rules.router, prefix=settings.API_V1_STR)
app.include_router(content.router, prefix=settings.API_V1_STR)
app.include_router(reviews.router, prefix=settings.API_V1_STR)
app.include_router(workflow.router, prefix=settings.API_V1_STR)
app.include_router(audit.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(insights.router, prefix=settings.API_V1_STR)
app.include_router(auth_routes.router, prefix=settings.API_V1_STR)
app.include_router(creatives.router, prefix=settings.API_V1_STR)
app.include_router(sources.router, prefix=settings.API_V1_STR)
app.include_router(intel.router, prefix=settings.API_V1_STR)

# Serve built frontend if dist directory exists
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    def serve_frontend_spa(full_path: str):
        # Allow /api to pass through
        if full_path.startswith("api"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        target_file = os.path.realpath(os.path.join(frontend_dist, full_path))
        if target_file.startswith(os.path.realpath(frontend_dist) + os.sep) and os.path.isfile(target_file):
            return FileResponse(target_file)
        # The shell must revalidate so a new deploy never runs against a stale bundle.
        return FileResponse(os.path.join(frontend_dist, "index.html"), headers={"Cache-Control": "no-cache"})
