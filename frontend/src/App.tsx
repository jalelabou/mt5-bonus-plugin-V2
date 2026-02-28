import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { BrokerProvider, useBroker } from "./context/BrokerContext";
import AppLayout from "./components/AppLayout";
import PlatformLayout from "./components/PlatformLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import CampaignList from "./pages/campaigns/CampaignList";
import CampaignForm from "./pages/campaigns/CampaignForm";
import CampaignDetail from "./pages/campaigns/CampaignDetail";
import BonusMonitor from "./pages/bonuses/BonusMonitor";
import AccountLookup from "./pages/accounts/AccountLookup";
import Reports from "./pages/reports/Reports";
import AuditLog from "./pages/audit/AuditLog";
import UserManagement from "./pages/settings/UserManagement";
import BrokerList from "./pages/platform/BrokerList";
import BrokerForm from "./pages/platform/BrokerForm";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function LoginGuard() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

function PlatformRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginGuard />} />
      <Route
        element={
          <ProtectedRoute>
            <PlatformLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<BrokerList />} />
        <Route path="/brokers/new" element={<BrokerForm />} />
        <Route path="/brokers/:id" element={<BrokerForm />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function BrokerRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginGuard />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/campaigns" element={<CampaignList />} />
        <Route path="/campaigns/new" element={<CampaignForm />} />
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
        <Route path="/campaigns/:id/edit" element={<CampaignForm />} />
        <Route path="/bonuses" element={<BonusMonitor />} />
        <Route path="/accounts" element={<AccountLookup />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/audit" element={<AuditLog />} />
        <Route path="/settings/users" element={<UserManagement />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function AppRoutes() {
  const { isPlatform } = useBroker();
  return isPlatform ? <PlatformRoutes /> : <BrokerRoutes />;
}

export default function App() {
  return (
    <ConfigProvider theme={{ token: { colorPrimary: "#1677ff" } }}>
      <BrowserRouter>
        <BrokerProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </BrokerProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
}
