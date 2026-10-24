# Vercel serverless entrypoint: exposes the FastAPI app for every /api/* request.
from backend.main import app  # noqa: F401
