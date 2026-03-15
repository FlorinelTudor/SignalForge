import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import AuthCallback from "@/pages/AuthCallback";
import DiscoverPage from "@/pages/DiscoverPage";
import AgentProfilePage from "@/pages/AgentProfilePage";
import DashboardPage from "@/pages/DashboardPage";
import PricingPage from "@/pages/PricingPage";
import VerifiedSuccessPage from "@/pages/VerifiedSuccessPage";
import LaunchPage from "@/pages/LaunchPage";
import VibePage from "@/pages/VibePage";

function AppRouter() {
  const location = useLocation();

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  // Check URL fragment synchronously for session_id - handles Google OAuth callback
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/discover" element={<DiscoverPage />} />
      <Route path="/agents/:agentId" element={<AgentProfilePage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/pricing" element={<PricingPage />} />
      <Route path="/verified/success" element={<VerifiedSuccessPage />} />
      <Route path="/launch" element={<LaunchPage />} />
      <Route path="/vibe" element={<VibePage />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRouter />
      <Toaster position="bottom-right" theme="dark" />
    </BrowserRouter>
  );
}

export default App;
