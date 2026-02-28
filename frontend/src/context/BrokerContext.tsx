import { createContext, useContext, ReactNode, useMemo } from "react";

interface BrokerContextType {
  slug: string;
  isPlatform: boolean;
}

const BrokerContext = createContext<BrokerContextType>({
  slug: "",
  isPlatform: false,
});

const PLATFORM_SLUGS = ["platform", "admin", "api", "localhost", "127"];

function detectBrokerSlug(): { slug: string; isPlatform: boolean } {
  // Dev override via env variable
  const envSlug = import.meta.env.VITE_BROKER_SLUG;
  if (envSlug) {
    const isPlatform = PLATFORM_SLUGS.includes(envSlug);
    return { slug: envSlug, isPlatform };
  }

  const hostname = window.location.hostname;

  // localhost / IP -> check for dev platform mode
  if (hostname === "localhost" || hostname === "127.0.0.1" || hostname.match(/^\d+\.\d+\.\d+\.\d+$/)) {
    // In dev, default to platform context unless VITE_BROKER_SLUG is set
    const envContext = import.meta.env.VITE_PLATFORM_MODE;
    if (envContext === "true") {
      return { slug: "platform", isPlatform: true };
    }
    // Default to broker context for backward compat
    return { slug: "default", isPlatform: false };
  }

  // Extract subdomain: broker1.domain.com -> "broker1"
  const parts = hostname.split(".");
  if (parts.length >= 3) {
    const subdomain = parts[0];
    if (PLATFORM_SLUGS.includes(subdomain)) {
      return { slug: subdomain, isPlatform: true };
    }
    return { slug: subdomain, isPlatform: false };
  }

  // No subdomain (bare domain) -> platform context
  return { slug: "platform", isPlatform: true };
}

export function BrokerProvider({ children }: { children: ReactNode }) {
  const context = useMemo(() => detectBrokerSlug(), []);

  return (
    <BrokerContext.Provider value={context}>
      {children}
    </BrokerContext.Provider>
  );
}

export const useBroker = () => useContext(BrokerContext);
