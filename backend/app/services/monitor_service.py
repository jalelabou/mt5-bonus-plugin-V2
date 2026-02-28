import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.registry import gateway_registry
from app.models.bonus import Bonus, BonusStatus
from app.models.monitored_account import MonitoredAccount
from app.services.bonus_engine import cancel_bonus
from app.services.trigger_service import process_deposit_trigger
from app.tasks.event_processor import process_deal_event

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_ERRORS = 5


async def register_for_monitoring(
    db: AsyncSession, mt5_login: str, reason: str = "active_bonus",
    broker_id: Optional[int] = None,
) -> MonitoredAccount:
    """Add or update an account in the monitoring table."""
    query = select(MonitoredAccount).where(MonitoredAccount.mt5_login == mt5_login)
    if broker_id is not None:
        query = query.where(MonitoredAccount.broker_id == broker_id)
    result = await db.execute(query)
    mon = result.scalar_one_or_none()

    gw = gateway_registry.require_gateway(broker_id) if broker_id else None

    if mon is None:
        # Fetch current snapshot from MT5
        account = await gw.get_account_info(mt5_login) if gw else None
        mon = MonitoredAccount(
            broker_id=broker_id,
            mt5_login=mt5_login,
            last_balance=account.balance if account else 0.0,
            last_equity=account.equity if account else 0.0,
            last_credit=account.credit if account else 0.0,
            last_deal_timestamp=0.0,
            is_active=True,
            monitor_reasons=[reason],
            last_polled_at=datetime.now(timezone.utc),
        )
        db.add(mon)
    else:
        # Refresh snapshot from MT5 to avoid stale data
        if gw:
            account = await gw.get_account_info(mt5_login)
            if account:
                mon.last_balance = account.balance
                mon.last_equity = account.equity
                mon.last_credit = account.credit
        reasons = mon.monitor_reasons or []
        if reason not in reasons:
            mon.monitor_reasons = reasons + [reason]
        mon.is_active = True
        mon.consecutive_errors = 0

    await db.flush()
    return mon


async def unregister_if_no_bonuses(db: AsyncSession, mt5_login: str, broker_id: Optional[int] = None):
    """Deactivate monitoring if account has no active bonuses."""
    bonus_query = select(Bonus.id).where(
        Bonus.mt5_login == mt5_login,
        Bonus.status == BonusStatus.ACTIVE,
    )
    if broker_id is not None:
        bonus_query = bonus_query.where(Bonus.broker_id == broker_id)
    active_q = await db.execute(bonus_query)
    if active_q.first() is not None:
        return  # Still has active bonuses

    mon_query = select(MonitoredAccount).where(MonitoredAccount.mt5_login == mt5_login)
    if broker_id is not None:
        mon_query = mon_query.where(MonitoredAccount.broker_id == broker_id)
    result = await db.execute(mon_query)
    mon = result.scalar_one_or_none()
    if mon:
        keep_reasons = {"deposit_watch", "auto_discovered"}
        remaining = [r for r in (mon.monitor_reasons or []) if r in keep_reasons]
        if not remaining:
            mon.is_active = False
            mon.monitor_reasons = []
        else:
            mon.monitor_reasons = remaining
        await db.flush()


async def poll_single_account(db: AsyncSession, mon: MonitoredAccount) -> dict:
    """
    Poll one monitored account. Returns summary of actions taken.
    Order: deposits -> withdrawal/drawdown -> Type C trades -> update snapshot.
    """
    broker_id = mon.broker_id
    gw = gateway_registry.require_gateway(broker_id)

    actions = {"login": mon.mt5_login, "broker_id": broker_id,
               "deposits": 0, "withdrawals": 0, "drawdowns": 0, "deals": 0}

    try:
        account = await gw.get_account_info(mon.mt5_login)
        if account is None:
            mon.consecutive_errors += 1
            mon.last_error = "Account not found in MT5"
            return actions

        # === DEPOSIT DETECTION ===
        balance_delta = account.balance - mon.last_balance
        logger.debug(
            "Poll %s (broker %d): bal=%.2f last=%.2f delta=%.2f credit=%.2f last_credit=%.2f",
            mon.mt5_login, broker_id, account.balance, mon.last_balance, balance_delta,
            account.credit, mon.last_credit,
        )
        if balance_delta > 0.01 and account.credit <= mon.last_credit + 0.01:
            balance_deals = await gw.get_balance_deals(
                mon.mt5_login, from_timestamp=mon.last_deal_timestamp
            )
            deposits_found = [d for d in balance_deals if d.amount > 0]

            if deposits_found:
                for deal in deposits_found:
                    logger.info(
                        "Auto-deposit detected: login=%s amount=%.2f deal=%s broker=%d",
                        mon.mt5_login, deal.amount, deal.deal_id, broker_id,
                    )
                    await process_deposit_trigger(db, mon.mt5_login, deal.amount, broker_id=broker_id)
                    actions["deposits"] += 1
                    if deal.timestamp > mon.last_deal_timestamp:
                        mon.last_deal_timestamp = deal.timestamp
            else:
                logger.info(
                    "Auto-deposit detected (via snapshot): login=%s amount=%.2f broker=%d",
                    mon.mt5_login, balance_delta, broker_id,
                )
                await process_deposit_trigger(db, mon.mt5_login, balance_delta, broker_id=broker_id)
                actions["deposits"] += 1

            # Re-fetch account after trigger may have posted credit
            account = await gw.get_account_info(mon.mt5_login)
            if account is None:
                mon.consecutive_errors += 1
                return actions

        # === WITHDRAWAL DETECTION ===
        if account.balance < mon.last_balance - 0.01:
            withdrawal_amount = mon.last_balance - account.balance
            logger.info(
                "Withdrawal detected: login=%s amount=%.2f broker=%d",
                mon.mt5_login, withdrawal_amount, broker_id,
            )
            await _cancel_all_bonuses_and_clear_credit(
                db, mon.mt5_login, broker_id,
                reason=f"withdrawal_detected:{withdrawal_amount:.2f}",
            )
            actions["withdrawals"] += 1
            account = await gw.get_account_info(mon.mt5_login)
            if account is None:
                mon.consecutive_errors += 1
                return actions

        # === DRAWDOWN DETECTION ===
        if account.credit > 0 and account.equity <= account.credit + 0.01:
            own_equity = account.equity - account.credit
            reason = (
                f"Drawdown breach: trader equity depleted. "
                f"Equity={account.equity:.2f}, Credit={account.credit:.2f}, "
                f"Trader own funds={own_equity:.2f}. "
                f"All trades closed and bonus credit removed."
            )
            logger.warning(
                "Drawdown breach: login=%s equity=%.2f <= credit=%.2f broker=%d — "
                "closing all trades and removing credit",
                mon.mt5_login, account.equity, account.credit, broker_id,
            )
            await _close_positions_and_clear_credit(
                db, mon.mt5_login, broker_id, reason=reason,
            )
            actions["drawdowns"] += 1
            account = await gw.get_account_info(mon.mt5_login)
            if account is None:
                mon.consecutive_errors += 1
                return actions

        # === ORPHANED CREDIT CLEANUP ===
        if account.credit > 0.01:
            active_bonuses = await _get_active_bonuses(db, mon.mt5_login, broker_id)
            if not active_bonuses:
                logger.info(
                    "Orphaned credit cleanup: login=%s credit=%.2f broker=%d (no active bonuses)",
                    mon.mt5_login, account.credit, broker_id,
                )
                await _force_remove_credit(mon.mt5_login, broker_id)
                account = await gw.get_account_info(mon.mt5_login)
                if account is None:
                    mon.consecutive_errors += 1
                    return actions

        # === TYPE C TRADE TRACKING ===
        type_c_bonuses = await _get_active_type_c_bonuses(db, mon.mt5_login, broker_id)
        if type_c_bonuses:
            trades = await gw.get_trade_history(
                mon.mt5_login, from_timestamp=mon.last_deal_timestamp
            )
            for deal in trades:
                await process_deal_event(db, deal, broker_id=broker_id)
                actions["deals"] += 1
                if deal.timestamp > mon.last_deal_timestamp:
                    mon.last_deal_timestamp = deal.timestamp

        # === UPDATE SNAPSHOT ===
        mon.last_balance = account.balance
        mon.last_equity = account.equity
        mon.last_credit = account.credit

        mon.last_polled_at = datetime.now(timezone.utc)
        mon.consecutive_errors = 0
        mon.last_error = None

    except Exception as e:
        mon.consecutive_errors += 1
        mon.last_error = str(e)[:500]
        logger.exception("Monitor poll failed: login=%s broker=%d", mon.mt5_login, broker_id)

    await db.flush()
    return actions


async def run_monitor_cycle(db: AsyncSession) -> dict:
    """Main entry point called by the scheduler. Polls all active monitored accounts across all brokers."""
    summary = {
        "total": 0, "deposits": 0, "withdrawals": 0,
        "drawdowns": 0, "deals": 0, "errors": 0,
    }

    # Iterate over all brokers with active gateways
    for broker_id in gateway_registry.get_all_broker_ids():
        gw = gateway_registry.get_gateway(broker_id)
        if not gw:
            continue

        # Auto-discover new MT5 accounts for this broker
        try:
            all_logins = await gw.get_all_logins()
            if all_logins:
                existing = await db.execute(
                    select(MonitoredAccount).where(MonitoredAccount.broker_id == broker_id)
                )
                existing_map = {m.mt5_login: m for m in existing.scalars().all()}
                for login in all_logins:
                    login_str = str(login)
                    if login_str not in existing_map:
                        await register_for_monitoring(db, login_str, reason="auto_discovered", broker_id=broker_id)
                        logger.info("Auto-discovered new MT5 account: %s (broker %d)", login_str, broker_id)
                    elif not existing_map[login_str].is_active:
                        mon = existing_map[login_str]
                        mon.is_active = True
                        if "auto_discovered" not in (mon.monitor_reasons or []):
                            mon.monitor_reasons = (mon.monitor_reasons or []) + ["auto_discovered"]
                        logger.info("Reactivated MT5 account: %s (broker %d)", login_str, broker_id)
                await db.flush()
        except Exception:
            logger.exception("Account auto-discovery failed for broker %d", broker_id)

    # Now poll all active monitored accounts (across all brokers)
    result = await db.execute(
        select(MonitoredAccount).where(
            MonitoredAccount.is_active == True,  # noqa: E712
            MonitoredAccount.consecutive_errors < MAX_CONSECUTIVE_ERRORS,
        ).order_by(MonitoredAccount.last_polled_at.asc().nullsfirst())
    )
    accounts = result.scalars().all()

    summary["total"] = len(accounts)
    for mon in accounts:
        poll_result = await poll_single_account(db, mon)
        summary["deposits"] += poll_result["deposits"]
        summary["withdrawals"] += poll_result["withdrawals"]
        summary["drawdowns"] += poll_result["drawdowns"]
        summary["deals"] += poll_result["deals"]
        if mon.consecutive_errors > 0:
            summary["errors"] += 1

    return summary


async def _close_positions_and_clear_credit(
    db: AsyncSession, mt5_login: str, broker_id: int, reason: str
):
    """Close all positions, cancel all bonuses, then remove credit with verification."""
    import asyncio as _asyncio

    gw = gateway_registry.require_gateway(broker_id)

    # Step 1: Close all open positions (try multiple times)
    for attempt in range(3):
        await gw.close_all_positions(mt5_login)
        await _asyncio.sleep(1.5)
        acct = await gw.get_account_info(mt5_login)
        if acct and abs(acct.equity - acct.balance - acct.credit) < 1.0:
            logger.info("Positions closed for %s (attempt %d)", mt5_login, attempt + 1)
            break
        logger.warning(
            "Positions may still be open for %s: equity=%.2f, balance+credit=%.2f (attempt %d)",
            mt5_login, acct.equity if acct else 0, (acct.balance + acct.credit) if acct else 0, attempt + 1,
        )

    # Step 2: Cancel all bonuses in DB
    await _cancel_all_bonuses_in_db(db, mt5_login, broker_id, reason)

    # Step 3: Remove credit with verification
    await _force_remove_credit(mt5_login, broker_id)

    # Unregister from monitoring if no bonuses left
    await unregister_if_no_bonuses(db, mt5_login, broker_id=broker_id)


async def _cancel_all_bonuses_and_clear_credit(
    db: AsyncSession, mt5_login: str, broker_id: int, reason: str
):
    """Cancel all active bonuses, then wipe any remaining credit from MT5."""
    await _cancel_all_bonuses_in_db(db, mt5_login, broker_id, reason)
    await _force_remove_credit(mt5_login, broker_id)
    await unregister_if_no_bonuses(db, mt5_login, broker_id=broker_id)


async def _cancel_all_bonuses_in_db(
    db: AsyncSession, mt5_login: str, broker_id: int, reason: str
):
    """Mark all active bonuses as cancelled in the DB."""
    gw = gateway_registry.require_gateway(broker_id)
    active_bonuses = await _get_active_bonuses(db, mt5_login, broker_id)

    now = datetime.now(timezone.utc)
    for bonus in active_bonuses:
        if bonus.bonus_type == "A" and bonus.original_leverage:
            from app.services.leverage_service import restore_leverage
            await restore_leverage(gw, bonus.mt5_login, bonus.original_leverage)

        bonus.status = BonusStatus.CANCELLED
        bonus.cancelled_at = now
        bonus.cancellation_reason = reason

        from app.models.audit_log import ActorType, EventType
        from app.services.audit_service import log_event
        await log_event(
            db,
            event_type=EventType.CANCELLATION,
            mt5_login=bonus.mt5_login,
            campaign_id=bonus.campaign_id,
            bonus_id=bonus.id,
            actor_type=ActorType.SYSTEM,
            before_state={"status": "active", "bonus_amount": bonus.bonus_amount},
            after_state={"status": "cancelled", "reason": reason},
            broker_id=broker_id,
        )

    await db.flush()


async def _force_remove_credit(mt5_login: str, broker_id: int):
    """Remove all credit from MT5 account, retrying and verifying after each attempt."""
    import asyncio as _asyncio

    gw = gateway_registry.require_gateway(broker_id)

    for attempt in range(5):
        account = await gw.get_account_info(mt5_login)
        if not account or account.credit <= 0.01:
            logger.info("Credit cleared for %s (credit=%.2f)", mt5_login, account.credit if account else 0)
            return

        # If positions are still open, close them first
        if abs(account.equity - account.balance - account.credit) > 1.0:
            logger.info(
                "Positions still open for %s before credit removal, closing... (attempt %d)",
                mt5_login, attempt + 1,
            )
            await gw.close_all_positions(mt5_login)
            await _asyncio.sleep(2)
            continue

        logger.info(
            "Removing credit: login=%s amount=%.2f (attempt %d)",
            mt5_login, account.credit, attempt + 1,
        )
        await gw.remove_credit(
            mt5_login, account.credit,
            "Bonus cancelled - credit removal",
        )
        await _asyncio.sleep(1.5)

        # Verify credit was actually removed
        check = await gw.get_account_info(mt5_login)
        if check and check.credit <= 0.01:
            logger.info("Credit verified removed for %s", mt5_login)
            return
        logger.warning(
            "Credit removal not confirmed for %s: credit still %.2f (attempt %d)",
            mt5_login, check.credit if check else -1, attempt + 1,
        )

    logger.error("Failed to remove credit for %s after 5 attempts", mt5_login)


async def _get_active_bonuses(db: AsyncSession, mt5_login: str, broker_id: Optional[int] = None):
    query = select(Bonus).where(
        Bonus.mt5_login == mt5_login,
        Bonus.status == BonusStatus.ACTIVE,
    )
    if broker_id is not None:
        query = query.where(Bonus.broker_id == broker_id)
    result = await db.execute(query)
    return result.scalars().all()


async def _get_active_type_c_bonuses(db: AsyncSession, mt5_login: str, broker_id: Optional[int] = None):
    query = select(Bonus).where(
        Bonus.mt5_login == mt5_login,
        Bonus.status == BonusStatus.ACTIVE,
        Bonus.bonus_type == "C",
    )
    if broker_id is not None:
        query = query.where(Bonus.broker_id == broker_id)
    result = await db.execute(query)
    return result.scalars().all()
