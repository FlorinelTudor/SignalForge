import { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { authAPI } from "@/lib/api";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = location.hash || window.location.hash;
    const params = new URLSearchParams(hash.replace('#', ''));
    const sessionId = params.get('session_id');

    if (!sessionId) {
      navigate('/login');
      return;
    }

    const processSession = async () => {
      try {
        const resp = await authAPI.googleCallback(sessionId);
        const { user } = resp.data;
        localStorage.setItem('user', JSON.stringify(user));
        navigate('/discover', { state: { user }, replace: true });
      } catch (err) {
        console.error('Auth callback error:', err);
        navigate('/login');
      }
    };
    processSession();
  }, [location, navigate]);

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-zinc-400 font-mono text-sm">Authenticating...</p>
      </div>
    </div>
  );
}
