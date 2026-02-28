"""Gateway registry — one MT5 connection per active broker."""
import logging
from typing import Dict, Optional

from app.gateway.interface import MT5Gateway

logger = logging.getLogger(__name__)


class GatewayRegistry:
    """Manages MT5Gateway instances keyed by broker_id."""

    def __init__(self):
        self._gateways: Dict[int, MT5Gateway] = {}

    async def register_broker(
        self,
        broker_id: int,
        bridge_url: str,
        mt5_server: str,
        manager_login: str,
        manager_password: str,
        request_timeout: int = 30,
    ) -> MT5Gateway:
        """Create and connect a RealMT5Gateway for a broker."""
        from app.gateway.real import RealMT5Gateway

        gw = RealMT5Gateway(
            bridge_url=bridge_url,
            mt5_server=mt5_server,
            manager_login=manager_login,
            manager_password=manager_password,
            request_timeout=request_timeout,
        )
        try:
            await gw.connect()
            self._gateways[broker_id] = gw
            logger.info(
                "Gateway registered for broker %d (bridge=%s server=%s)",
                broker_id, bridge_url, mt5_server,
            )
        except Exception:
            logger.exception("Failed to connect gateway for broker %d", broker_id)
            raise
        return gw

    def register_mock(self, broker_id: int) -> MT5Gateway:
        """Register a MockMT5Gateway for a broker (dev/testing)."""
        from app.gateway.mock import MockMT5Gateway

        gw = MockMT5Gateway()
        self._gateways[broker_id] = gw
        logger.info("Mock gateway registered for broker %d", broker_id)
        return gw

    def get_gateway(self, broker_id: int) -> Optional[MT5Gateway]:
        """Get the gateway for a broker. Returns None if not registered."""
        return self._gateways.get(broker_id)

    def require_gateway(self, broker_id: int) -> MT5Gateway:
        """Get gateway or raise if not found."""
        gw = self._gateways.get(broker_id)
        if gw is None:
            raise RuntimeError(f"No MT5 gateway registered for broker {broker_id}")
        return gw

    async def unregister_broker(self, broker_id: int) -> None:
        """Disconnect and remove a broker's gateway."""
        gw = self._gateways.pop(broker_id, None)
        if gw and hasattr(gw, "disconnect"):
            try:
                await gw.disconnect()
            except Exception:
                logger.exception("Error disconnecting gateway for broker %d", broker_id)
        logger.info("Gateway unregistered for broker %d", broker_id)

    async def refresh_broker(
        self,
        broker_id: int,
        bridge_url: str,
        mt5_server: str,
        manager_login: str,
        manager_password: str,
        request_timeout: int = 30,
    ) -> MT5Gateway:
        """Disconnect old gateway and create a new one (e.g. after cred change)."""
        await self.unregister_broker(broker_id)
        return await self.register_broker(
            broker_id, bridge_url, mt5_server, manager_login, manager_password, request_timeout
        )

    async def shutdown_all(self) -> None:
        """Disconnect all gateways. Called on app shutdown."""
        for broker_id in list(self._gateways.keys()):
            await self.unregister_broker(broker_id)
        logger.info("All gateways shut down")

    def get_all_broker_ids(self) -> list[int]:
        """Return list of broker IDs with active gateways."""
        return list(self._gateways.keys())

    def __len__(self) -> int:
        return len(self._gateways)


# Module-level singleton
gateway_registry = GatewayRegistry()
