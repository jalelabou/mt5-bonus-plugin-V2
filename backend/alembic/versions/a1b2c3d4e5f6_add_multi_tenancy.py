"""Add multi-tenancy support

Revision ID: a1b2c3d4e5f6
Revises: 9a1306627ed4
Create Date: 2026-02-27 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9a1306627ed4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create brokers table
    op.create_table(
        'brokers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('mt5_bridge_url', sa.String(length=500), nullable=True),
        sa.Column('mt5_server', sa.String(length=255), nullable=True),
        sa.Column('mt5_manager_login', sa.String(length=100), nullable=True),
        sa.Column('mt5_manager_password', sa.String(length=255), nullable=True),
        sa.Column('api_key', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_brokers_slug'), 'brokers', ['slug'], unique=True)
    op.create_index(op.f('ix_brokers_api_key'), 'brokers', ['api_key'], unique=True)

    # 2. Insert default broker for existing data
    op.execute(
        "INSERT INTO brokers (id, name, slug, is_active) VALUES (1, 'Default Broker', 'default', 1)"
    )

    # 3. Add broker_id + is_broker_admin to admin_users
    op.add_column('admin_users', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.add_column('admin_users', sa.Column('is_broker_admin', sa.Boolean(), nullable=True, server_default=sa.text('0')))
    op.create_index('ix_admin_users_broker_id', 'admin_users', ['broker_id'], unique=False)

    # 4. Add broker_id to campaigns
    op.add_column('campaigns', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.execute("UPDATE campaigns SET broker_id = 1")
    op.create_index('ix_campaigns_broker_id', 'campaigns', ['broker_id'], unique=False)

    # 5. Add broker_id to bonuses
    op.add_column('bonuses', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.execute("UPDATE bonuses SET broker_id = 1 WHERE broker_id IS NULL")
    op.create_index('ix_bonuses_broker_id', 'bonuses', ['broker_id'], unique=False)

    # 6. Add broker_id to bonus_lot_progress
    op.add_column('bonus_lot_progress', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.execute("UPDATE bonus_lot_progress SET broker_id = 1 WHERE broker_id IS NULL")
    op.create_index('ix_bonus_lot_progress_broker_id', 'bonus_lot_progress', ['broker_id'], unique=False)

    # 7. Add broker_id to trigger_events
    op.add_column('trigger_events', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.execute("UPDATE trigger_events SET broker_id = 1 WHERE broker_id IS NULL")
    op.create_index('ix_trigger_events_broker_id', 'trigger_events', ['broker_id'], unique=False)

    # 8. Add broker_id to audit_logs (nullable — platform events have no broker)
    op.add_column('audit_logs', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.execute("UPDATE audit_logs SET broker_id = 1 WHERE broker_id IS NULL")
    op.create_index('ix_audit_logs_broker_id', 'audit_logs', ['broker_id'], unique=False)

    # 9. Add broker_id to monitored_accounts
    op.add_column('monitored_accounts', sa.Column('broker_id', sa.Integer(), nullable=True))
    op.execute("UPDATE monitored_accounts SET broker_id = 1 WHERE broker_id IS NULL")
    op.create_index('ix_monitored_accounts_broker_id', 'monitored_accounts', ['broker_id'], unique=False)
    # Drop old unique index on mt5_login, replace with non-unique + composite unique
    op.drop_index('ix_monitored_accounts_mt5_login', table_name='monitored_accounts')
    op.create_index('ix_monitored_accounts_mt5_login', 'monitored_accounts', ['mt5_login'], unique=False)
    # Use unique index instead of constraint (SQLite compatible)
    op.create_index('uq_monitored_mt5_broker', 'monitored_accounts', ['mt5_login', 'broker_id'], unique=True)


def downgrade() -> None:
    # monitored_accounts
    op.drop_index('uq_monitored_mt5_broker', table_name='monitored_accounts')
    op.drop_index('ix_monitored_accounts_mt5_login', table_name='monitored_accounts')
    op.create_index('ix_monitored_accounts_mt5_login', 'monitored_accounts', ['mt5_login'], unique=True)
    op.drop_index('ix_monitored_accounts_broker_id', table_name='monitored_accounts')
    op.drop_column('monitored_accounts', 'broker_id')

    # audit_logs
    op.drop_index('ix_audit_logs_broker_id', table_name='audit_logs')
    op.drop_column('audit_logs', 'broker_id')

    # trigger_events
    op.drop_index('ix_trigger_events_broker_id', table_name='trigger_events')
    op.drop_column('trigger_events', 'broker_id')

    # bonus_lot_progress
    op.drop_index('ix_bonus_lot_progress_broker_id', table_name='bonus_lot_progress')
    op.drop_column('bonus_lot_progress', 'broker_id')

    # bonuses
    op.drop_index('ix_bonuses_broker_id', table_name='bonuses')
    op.drop_column('bonuses', 'broker_id')

    # campaigns
    op.drop_index('ix_campaigns_broker_id', table_name='campaigns')
    op.drop_column('campaigns', 'broker_id')

    # admin_users
    op.drop_index('ix_admin_users_broker_id', table_name='admin_users')
    op.drop_column('admin_users', 'is_broker_admin')
    op.drop_column('admin_users', 'broker_id')

    # brokers table
    op.drop_index(op.f('ix_brokers_api_key'), table_name='brokers')
    op.drop_index(op.f('ix_brokers_slug'), table_name='brokers')
    op.drop_table('brokers')
