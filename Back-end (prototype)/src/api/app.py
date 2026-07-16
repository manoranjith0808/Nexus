"""FastAPI application — main entry point for the Sentinel Swarm API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel_swarm.api.routes import tenants, events, cases, graph, training, health, alerts, reports, prometeo
from sentinel_swarm.api.deps import startup, shutdown


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield
    shutdown()


app = FastAPI(
    title="Sentinel Swarm API",
    description="AROS — Autonomous Risk Operating System for real-time financial fraud detection",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health.router, tags=["Health"])
app.include_router(tenants.router, prefix="/api/tenants", tags=["Tenants"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(graph.router, prefix="/api/graph", tags=["Graph"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(prometeo.router, prefix="/api/prometeo", tags=["Prometeo"])
app.include_router(training.router, prefix="/api/training", tags=["Training"])
