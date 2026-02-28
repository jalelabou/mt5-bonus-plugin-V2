import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config.settings import settings
from app.api import auth, campaigns, bonuses, accounts, reports, audit, triggers, monitoring, platform, users
from app.middleware.broker_context import BrokerContextMiddleware
from app.tasks.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.gateway.registry import gateway_registry
    from app.db.database import async_session
    from app.models.broker import Broker

    # Register gateways for all active brokers
    async with async_session() as db:
        result = await db.execute(
            select(Broker).where(Broker.is_active == True)
        )
        brokers = result.scalars().all()

    for broker in brokers:
        if broker.mt5_configured:
            try:
                await gateway_registry.register_broker(
                    broker_id=broker.id,
                    bridge_url=broker.mt5_bridge_url,
                    mt5_server=broker.mt5_server,
                    manager_login=broker.mt5_manager_login,
                    manager_password=broker.mt5_manager_password,
                )
            except Exception:
                logger.exception("Failed to connect gateway for broker %d (%s)", broker.id, broker.slug)
        else:
            # No MT5 creds configured — register mock for dev
            gateway_registry.register_mock(broker.id)
            logger.info("Broker %d (%s) has no MT5 config, using mock gateway", broker.id, broker.slug)

    logger.info("Gateway registry initialized: %d brokers", len(gateway_registry))

    start_scheduler()
    yield
    stop_scheduler()
    await gateway_registry.shutdown_all()


app = FastAPI(
    title="MT5 Bonus Plugin",
    description="Multi-tenant broker bonus campaign management for MetaTrader 5",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(BrokerContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(bonuses.router)
app.include_router(accounts.router)
app.include_router(reports.router)
app.include_router(audit.router)
app.include_router(triggers.router)
app.include_router(monitoring.router)
app.include_router(platform.router)
app.include_router(users.router)


@app.get("/api/health")
async def health():
    from app.tasks.scheduler import scheduler
    from app.gateway.registry import gateway_registry

    monitor_job = scheduler.get_job("account_monitor")
    return {
        "status": "ok",
        "service": "mt5-bonus-plugin-v2",
        "scheduler_running": scheduler.running,
        "active_brokers": len(gateway_registry),
        "broker_ids": gateway_registry.get_all_broker_ids(),
        "monitor_active": monitor_job is not None,
    }
