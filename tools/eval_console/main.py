import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from auth import check_reviewer_password, make_token
from db import init_db
from data.loader import load_data
from models import LoginRequest
from routes.export import router as export_router
from routes.progress import router as progress_router
from routes.queries import router as queries_router
from routes.ratings import router as ratings_router

_FRONTEND = Path(__file__).parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_data()
    yield


app = FastAPI(
    title="LEO Expert Evaluation Console",
    description="Blinded expert evaluation interface for the LEO benchmark",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(queries_router)
app.include_router(ratings_router)
app.include_router(progress_router)
app.include_router(export_router)

# Static JS files
app.mount("/js", StaticFiles(directory=str(_FRONTEND / "js")), name="js")


@app.post("/auth/login")
async def login(req: LoginRequest):
    if not check_reviewer_password(req.reviewer_id, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_token(req.reviewer_id), "reviewer_id": req.reviewer_id}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    return (_FRONTEND / "index.html").read_text(encoding="utf-8")


@app.get("/review", response_class=HTMLResponse, include_in_schema=False)
async def review():
    return (_FRONTEND / "review.html").read_text(encoding="utf-8")


@app.get("/progress", response_class=HTMLResponse, include_in_schema=False)
async def progress_page():
    return (_FRONTEND / "progress.html").read_text(encoding="utf-8")
