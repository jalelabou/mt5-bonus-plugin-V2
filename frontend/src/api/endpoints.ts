import api from "./client";
import type {
  Bonus,
  BonusDetail,
  Broker,
  BrokerCreate,
  BrokerAdminCreate,
  Campaign,
  CampaignListItem,
  PaginatedResponse,
  TokenResponse,
  AuditLogEntry,
  User,
  UserCreate,
} from "../types";

// Auth
export const login = (email: string, password: string) =>
  api.post<TokenResponse>("/auth/login", { email, password });

export const getMe = () => api.get<User>("/auth/me");

// Campaigns
export const getCampaigns = (params?: Record<string, unknown>) =>
  api.get<PaginatedResponse<CampaignListItem>>("/campaigns", { params });

export const getCampaign = (id: number) =>
  api.get<Campaign>(`/campaigns/${id}`);

export const createCampaign = (data: Partial<Campaign>) =>
  api.post<Campaign>("/campaigns", data);

export const updateCampaign = (id: number, data: Partial<Campaign>) =>
  api.put<Campaign>(`/campaigns/${id}`, data);

export const duplicateCampaign = (id: number) =>
  api.post<Campaign>(`/campaigns/${id}/duplicate`);

export const updateCampaignStatus = (id: number, status: string) =>
  api.patch<Campaign>(`/campaigns/${id}/status`, { status });

// Bonuses
export const getBonuses = (params?: Record<string, unknown>) =>
  api.get<PaginatedResponse<Bonus>>("/bonuses", { params });

export const getBonus = (id: number) =>
  api.get<BonusDetail>(`/bonuses/${id}`);

export const assignBonus = (data: { campaign_id: number; mt5_login: string; deposit_amount?: number }) =>
  api.post<Bonus>("/bonuses/assign", data);

export const cancelBonus = (id: number, reason: string) =>
  api.post<Bonus>(`/bonuses/${id}/cancel`, { reason });

export const forceConvert = (id: number) =>
  api.post<Bonus>(`/bonuses/${id}/force-convert`);

export const overrideLeverage = (id: number, newLeverage: number) =>
  api.post<Bonus>(`/bonuses/${id}/override-leverage`, { new_leverage: newLeverage });

// Accounts
export const getAccount = (login: string) =>
  api.get(`/accounts/${login}`);

export const getMT5Metadata = () =>
  api.get<{ groups: string[]; countries: string[]; accounts: { login: string; name: string; group: string; country: string }[] }>("/accounts/mt5-metadata");

// Reports
export const getReportSummary = (params?: Record<string, unknown>) =>
  api.get("/reports/summary", { params });

export const getReportConversions = (params?: Record<string, unknown>) =>
  api.get("/reports/conversions", { params });

export const getReportCancellations = (params?: Record<string, unknown>) =>
  api.get("/reports/cancellations", { params });

export const getReportLeverage = () =>
  api.get("/reports/leverage");

export const exportReport = (reportType: string, format: string, params?: Record<string, unknown>) =>
  api.get("/reports/export", { params: { report_type: reportType, format, ...params }, responseType: "blob" });

// Audit
export const getAuditLogs = (params?: Record<string, unknown>) =>
  api.get<PaginatedResponse<AuditLogEntry>>("/audit", { params });

// Triggers
export const triggerDeposit = (mt5_login: string, deposit_amount: number, agent_code?: string) =>
  api.post("/triggers/deposit", { mt5_login, deposit_amount, agent_code });

export const triggerRegistration = (mt5_login: string) =>
  api.post("/triggers/registration", { mt5_login });

export const triggerPromoCode = (mt5_login: string, promo_code: string, deposit_amount?: number) =>
  api.post("/triggers/promo-code", { mt5_login, promo_code, deposit_amount });

// Platform — Broker Management (Super Admin only)
export const getPlatformBrokers = () =>
  api.get<Broker[]>("/platform/brokers");

export const createPlatformBroker = (data: BrokerCreate) =>
  api.post<Broker>("/platform/brokers", data);

export const getPlatformBroker = (id: number) =>
  api.get<Broker>(`/platform/brokers/${id}`);

export const updatePlatformBroker = (id: number, data: Partial<BrokerCreate>) =>
  api.put<Broker>(`/platform/brokers/${id}`, data);

export const toggleBrokerStatus = (id: number) =>
  api.patch<Broker>(`/platform/brokers/${id}/status`);

export const createBrokerAdmin = (brokerId: number, data: BrokerAdminCreate) =>
  api.post<User>(`/platform/brokers/${brokerId}/admin`, data);

export const getBrokerAdmins = (brokerId: number) =>
  api.get<User[]>(`/platform/brokers/${brokerId}/admins`);

// User Management (Broker Admin)
export const getUsers = () =>
  api.get<User[]>("/users");

export const createUser = (data: UserCreate) =>
  api.post<User>("/users", data);

export const updateUser = (id: number, data: Partial<{ full_name: string; role: string; is_active: boolean }>) =>
  api.put<User>(`/users/${id}`, data);

export const deactivateUser = (id: number) =>
  api.delete(`/users/${id}`);

// Health
export const getHealth = () => api.get<{ status: string; scheduler_running: boolean }>("/health");

// Gateway
export const getMockAccounts = () => api.get("/gateway/accounts");
