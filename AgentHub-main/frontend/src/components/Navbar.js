import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { authAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Shield, Home, Search, LayoutDashboard, LogOut, User, ChevronDown, Sparkles, Zap } from "lucide-react";

export const Navbar = () => {
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const stored = localStorage.getItem("user");
    if (stored) {
      try { setUser(JSON.parse(stored)); } catch {}
    }
  }, []);

  const handleLogout = async () => {
    try { await authAPI.logout(); } catch {}
    localStorage.removeItem("user");
    navigate("/");
  };

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="fixed top-0 w-full z-50 glass-strong" data-testid="navbar">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2" data-testid="nav-logo">
            <Shield className="w-5 h-5 text-cyan-400" />
            <span className="text-lg font-bold tracking-tight" style={{ fontFamily: 'Space Grotesk' }}>AgentXplorer</span>
          </Link>
          <div className="hidden md:flex items-center gap-1">
            {location.pathname !== "/" && (
              <Link to="/" data-testid="nav-home">
                <Button variant="ghost" className="rounded-none text-sm h-9 text-zinc-400 hover:text-white">
                  <Home className="w-3.5 h-3.5 mr-1.5" /> Home
                </Button>
              </Link>
            )}
            <Link to="/pricing" data-testid="nav-pricing">
              <Button variant="ghost" className={`rounded-none text-sm h-9 ${isActive('/pricing') ? 'text-cyan-400 bg-cyan-400/5' : 'text-zinc-400 hover:text-white'}`}>
                <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Pricing
              </Button>
            </Link>
            <Link to="/vibe" data-testid="nav-vibe">
              <Button variant="ghost" className={`rounded-none text-sm h-9 ${isActive('/vibe') ? 'text-cyan-400 bg-cyan-400/5' : 'text-zinc-400 hover:text-white'}`}>
                <Zap className="w-3.5 h-3.5 mr-1.5" /> Vibe Pro
              </Button>
            </Link>
            <Link to="/launch" data-testid="nav-launch">
              <Button variant="ghost" className={`rounded-none text-sm h-9 ${isActive('/launch') ? 'text-cyan-400 bg-cyan-400/5' : 'text-zinc-400 hover:text-white'}`}>
                Launch
              </Button>
            </Link>
            <Link to="/discover" data-testid="nav-discover">
              <Button variant="ghost" className={`rounded-none text-sm h-9 ${isActive('/discover') ? 'text-cyan-400 bg-cyan-400/5' : 'text-zinc-400 hover:text-white'}`}>
                <Search className="w-3.5 h-3.5 mr-1.5" /> Discover
              </Button>
            </Link>
            {user && (
              <Link to="/dashboard" data-testid="nav-dashboard">
                <Button variant="ghost" className={`rounded-none text-sm h-9 ${isActive('/dashboard') ? 'text-cyan-400 bg-cyan-400/5' : 'text-zinc-400 hover:text-white'}`}>
                  <LayoutDashboard className="w-3.5 h-3.5 mr-1.5" /> Dashboard
                </Button>
              </Link>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="rounded-none text-sm text-zinc-400 hover:text-white h-9 gap-2" data-testid="user-menu-trigger">
                  {user.picture ? (
                    <img src={user.picture} alt="" className="w-6 h-6 rounded-full" />
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-cyan-400/20 flex items-center justify-center text-cyan-400 text-xs font-bold">
                      {user.name?.[0]?.toUpperCase() || "U"}
                    </div>
                  )}
                  <span className="hidden sm:inline">{user.name}</span>
                  <ChevronDown className="w-3 h-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="bg-[#0a0a0b] border-zinc-800 w-48">
                <DropdownMenuItem onClick={() => navigate('/dashboard')} className="text-zinc-300 focus:bg-zinc-800 focus:text-white cursor-pointer" data-testid="menu-dashboard">
                  <LayoutDashboard className="w-4 h-4 mr-2" /> Dashboard
                </DropdownMenuItem>
                <DropdownMenuSeparator className="bg-zinc-800" />
                <DropdownMenuItem onClick={handleLogout} className="text-red-400 focus:bg-red-400/10 focus:text-red-400 cursor-pointer" data-testid="menu-logout">
                  <LogOut className="w-4 h-4 mr-2" /> Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <>
              <Button variant="ghost" onClick={() => navigate('/login')} className="text-zinc-400 hover:text-white rounded-none text-sm h-9" data-testid="nav-login-btn">
                Sign In
              </Button>
              <Button onClick={() => navigate('/register')} className="bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none btn-skew h-9 px-4 text-sm" data-testid="nav-register-btn">
                <span>Get Started</span>
              </Button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};
