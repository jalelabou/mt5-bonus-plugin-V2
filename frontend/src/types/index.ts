export type AdminRole = "super_admin" | "campaign_manager" | "support_agent" | "read_only";
export type CampaignStatus = "draft" | "active" | "paused" | "ended" | "archived";
export type BonusType = "A" | "B" | "C";
export type BonusStatusType = "active" | "converted" | "cancelled" | "expired";
export type LotTrackingScope = "all" | "post_bonus" | "symbol_filtered" | "per_trade_threshold";
export type EventType = "assignment" | "cancellation" | "conversion_step" | "leverage_change" | "expiry" | "admin_override";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: AdminRole;
  is_active: boolean;
  broker_id: number | null;
  is_broker_admin: boolean;
  created_at: string;
}

export interface Broker {
  id: number;
  name: string;
  slug: string;
  contact_email: string | null;
  contact_phone: string | null;
  mt5_bridge_url: string | null;
  mt5_server: string | null;
  mt5_manager_login: string | null;
  api_key: string | null;
  is_active: boolean;
  mt5_configured: boolean;
  created_at: string;
  updated_at: string;
}

export interface BrokerCreate {
  name: string;
  slug: string;
  contact_email?: string;
  contact_phone?: string;
  mt5_bridge_url?: string;
  mt5_server?: string;
  mt5_manager_login?: string;
  mt5_manager_password?: string;
}

export interface BrokerAdminCreate {
  email: string;
  password: string;
  full_name: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name: string;
  role?: AdminRole;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface Campaign {
  id: number;
  name: string;
  status: CampaignStatus;
  bonus_type: BonusType;
  bonus_percentage: number;
  max_bonus_amount: number | null;
  min_deposit: number | null;
  max_deposit: number | null;
  lot_requirement: number | null;
  lot_tracking_scope: LotTrackingScope | null;
  symbol_filter: string[] | null;
  per_trade_lot_minimum: number | null;
  start_date: string | null;
  end_date: string | null;
  expiry_days: number | null;
  target_mt5_groups: string[] | null;
  target_countries: string[] | null;
  trigger_types: string[];
  promo_code: string | null;
  agent_codes: string[] | null;
  one_bonus_per_account: boolean;
  max_concurrent_bonuses: number;
  notes: string | null;
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
  active_bonus_count?: number;
}

export interface CampaignListItem {
  id: number;
  name: string;
  status: CampaignStatus;
  bonus_type: BonusType;
  bonus_percentage: number;
  start_date: string | null;
  end_date: string | null;
  active_bonus_count: number;
  created_at: string;
}

export interface Bonus {
  id: number;
  campaign_id: number;
  campaign_name?: string;
  mt5_login: string;
  bonus_type: string;
  bonus_amount: number;
  original_leverage: number | null;
  adjusted_leverage: number | null;
  lots_required: number | null;
  lots_traded: number;
  amount_converted: number;
  status: BonusStatusType;
  assigned_at: string;
  expires_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  percent_converted?: number;
}

export interface LotProgress {
  id: number;
  deal_id: string;
  symbol: string;
  lots: number;
  amount_converted: number;
  created_at: string;
}

export interface BonusDetail extends Bonus {
  lot_progress: LotProgress[];
}

export interface AuditLogEntry {
  id: number;
  actor_type: string;
  actor_id: number | null;
  mt5_login: string | null;
  campaign_id: number | null;
  bonus_id: number | null;
  event_type: EventType;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  metadata_: Record<string, unknown> | null;
  created_at: string;
}

export interface MT5Account {
  login: string;
  name: string;
  balance: number;
  equity: number;
  credit: number;
  leverage: number;
  group: string;
  country: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
