"""Seed script to create initial data for multi-tenant setup."""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password
from app.db.database import async_session, engine
from app.db.base import Base
from app.models.broker import Broker
from app.models.user import AdminRole, AdminUser
from app.models.campaign import Campaign, CampaignStatus, BonusType, LotTrackingScope


async def seed():
    # Create tables directly (for dev without Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # === 1. Create default broker ===
        result = await db.execute(select(Broker).where(Broker.slug == "default"))
        default_broker = result.scalar_one_or_none()
        if not default_broker:
            default_broker = Broker(
                name="Default Broker",
                slug="default",
                mt5_bridge_url="http://135.181.217.184:5000",
                mt5_server="173.234.17.76",
                mt5_manager_login="3333",
                mt5_manager_password="C@Im0hBo",
                is_active=True,
            )
            db.add(default_broker)
            await db.flush()
            print(f"  Default broker created (id={default_broker.id})")
        else:
            print(f"  Default broker already exists (id={default_broker.id})")

        # === 2. Create platform super admin (broker_id=NULL) ===
        result = await db.execute(
            select(AdminUser).where(AdminUser.email == "platform@mt5bonus.com")
        )
        if not result.scalar_one_or_none():
            platform_admin = AdminUser(
                email="platform@mt5bonus.com",
                password_hash=hash_password("platform123"),
                full_name="Platform Super Admin",
                role=AdminRole.SUPER_ADMIN,
                broker_id=None,  # Platform-level — no broker
            )
            db.add(platform_admin)
            print("  Platform super admin created: platform@mt5bonus.com / platform123")
        else:
            print("  Platform super admin already exists")

        # === 3. Create broker admin + sub-admins for default broker ===
        result = await db.execute(
            select(AdminUser).where(AdminUser.email == "admin@mt5bonus.com")
        )
        existing_admin = result.scalar_one_or_none()
        if existing_admin:
            # Migrate existing admin to be broker-scoped
            if existing_admin.broker_id is None:
                existing_admin.broker_id = default_broker.id
                existing_admin.is_broker_admin = True
                print("  Migrated admin@mt5bonus.com to default broker admin")
            else:
                print("  admin@mt5bonus.com already scoped to broker")
        else:
            admin = AdminUser(
                email="admin@mt5bonus.com",
                password_hash=hash_password("admin123"),
                full_name="Broker Admin",
                role=AdminRole.SUPER_ADMIN,
                broker_id=default_broker.id,
                is_broker_admin=True,
            )
            db.add(admin)
            print("  Broker admin created: admin@mt5bonus.com / admin123")

        # Sub-admins for the default broker
        sub_admins = [
            ("manager@mt5bonus.com", "manager123", "Campaign Manager", AdminRole.CAMPAIGN_MANAGER),
            ("support@mt5bonus.com", "support123", "Support Agent", AdminRole.SUPPORT_AGENT),
            ("viewer@mt5bonus.com", "viewer123", "Read Only User", AdminRole.READ_ONLY),
        ]
        for email, pwd, name, role in sub_admins:
            result = await db.execute(select(AdminUser).where(AdminUser.email == email))
            user = result.scalar_one_or_none()
            if user:
                if user.broker_id is None:
                    user.broker_id = default_broker.id
                    print(f"  Migrated {email} to default broker")
            else:
                db.add(AdminUser(
                    email=email,
                    password_hash=hash_password(pwd),
                    full_name=name,
                    role=role,
                    broker_id=default_broker.id,
                ))
                print(f"  Created {email} / {pwd}")

        await db.flush()

        # Get broker admin for campaign created_by
        result = await db.execute(
            select(AdminUser).where(AdminUser.email == "admin@mt5bonus.com")
        )
        admin = result.scalar_one()

        # === 4. Create sample campaigns (scoped to default broker) ===
        result = await db.execute(
            select(Campaign).where(Campaign.broker_id == default_broker.id)
        )
        existing_campaigns = result.scalars().all()
        if existing_campaigns:
            print(f"  Campaigns already exist ({len(existing_campaigns)}), skipping")
        else:
            campaigns = [
                Campaign(
                    name="Welcome Bonus 100%",
                    status=CampaignStatus.ACTIVE,
                    bonus_type=BonusType.TYPE_B,
                    bonus_percentage=100.0,
                    max_bonus_amount=5000.0,
                    min_deposit=100.0,
                    max_deposit=10000.0,
                    trigger_types=["auto_deposit", "registration"],
                    target_mt5_groups=["demo\\standard", "demo\\premium"],
                    one_bonus_per_account=True,
                    max_concurrent_bonuses=1,
                    notes="Welcome bonus for new accounts",
                    created_by_id=admin.id,
                    broker_id=default_broker.id,
                ),
                Campaign(
                    name="VIP Leverage Boost 50%",
                    status=CampaignStatus.ACTIVE,
                    bonus_type=BonusType.TYPE_A,
                    bonus_percentage=50.0,
                    max_bonus_amount=25000.0,
                    min_deposit=5000.0,
                    trigger_types=["auto_deposit"],
                    target_mt5_groups=["demo\\vip", "live\\vip"],
                    one_bonus_per_account=False,
                    max_concurrent_bonuses=2,
                    expiry_days=90,
                    notes="VIP dynamic leverage bonus",
                    created_by_id=admin.id,
                    broker_id=default_broker.id,
                ),
                Campaign(
                    name="Trade & Earn Convertible",
                    status=CampaignStatus.ACTIVE,
                    bonus_type=BonusType.TYPE_C,
                    bonus_percentage=50.0,
                    max_bonus_amount=2500.0,
                    min_deposit=500.0,
                    lot_requirement=10.0,
                    lot_tracking_scope=LotTrackingScope.POST_BONUS,
                    trigger_types=["auto_deposit"],
                    target_mt5_groups=["demo\\standard", "live\\standard"],
                    one_bonus_per_account=True,
                    max_concurrent_bonuses=1,
                    expiry_days=60,
                    notes="Convertible bonus - trade 10 lots to convert",
                    created_by_id=admin.id,
                    broker_id=default_broker.id,
                ),
                Campaign(
                    name="Promo Code Special",
                    status=CampaignStatus.ACTIVE,
                    bonus_type=BonusType.TYPE_B,
                    bonus_percentage=200.0,
                    max_bonus_amount=1000.0,
                    min_deposit=200.0,
                    trigger_types=["promo_code"],
                    promo_code="BONUS200",
                    one_bonus_per_account=True,
                    max_concurrent_bonuses=2,
                    notes="200% bonus with promo code BONUS200",
                    created_by_id=admin.id,
                    broker_id=default_broker.id,
                ),
                Campaign(
                    name="IB Referral Bonus",
                    status=CampaignStatus.DRAFT,
                    bonus_type=BonusType.TYPE_B,
                    bonus_percentage=30.0,
                    max_bonus_amount=3000.0,
                    trigger_types=["agent_code"],
                    agent_codes=["IB001", "IB002", "IB003"],
                    one_bonus_per_account=True,
                    max_concurrent_bonuses=1,
                    notes="Agent/IB referral bonus - draft",
                    created_by_id=admin.id,
                    broker_id=default_broker.id,
                ),
            ]
            for c in campaigns:
                db.add(c)
            print(f"  Campaigns: {len(campaigns)} created")

        await db.commit()
        print("\nSeed complete!")
        print("  Platform admin: platform@mt5bonus.com / platform123")
        print("  Broker admin:   admin@mt5bonus.com / admin123")
        print("  Sub-admins:     manager@ / support@ / viewer@ (same passwords)")


if __name__ == "__main__":
    asyncio.run(seed())
