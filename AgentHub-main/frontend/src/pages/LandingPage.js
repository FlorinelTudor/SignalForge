import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Shield, ArrowRight, Zap, BarChart3, Users, Lock, Search, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { metaAPI } from "@/lib/api";

export default function LandingPage() {
  const [stats, setStats] = useState({ total_agents: 0, total_deployments: 0, total_reviews: 0 });
  const navigate = useNavigate();

  useEffect(() => {
    metaAPI.stats().then(r => setStats(r.data)).catch(() => {});
    // Auto-seed on first visit
    metaAPI.seed().catch(() => {});
    // Warm up backend (prevents cold start delays)
    metaAPI.stats().catch(() => {});
  }, []);

  const features = [
    { icon: Shield, title: "Trust Scores", desc: "Composite reputation based on real metrics: task completion, security audits, uptime, and user satisfaction.", color: "text-cyan-400" },
    { icon: BarChart3, title: "Verified Benchmarks", desc: "Skills validated through independent testing, not self-reported. Every number is auditable.", color: "text-violet-400" },
    { icon: Users, title: "Agent Network", desc: "Discover which agents work well together with verified integration data and deployment patterns.", color: "text-rose-400" },
    { icon: Lock, title: "Transparency First", desc: "Full incident history, red flags, and security audit status. No hidden surprises.", color: "text-emerald-400" },
    { icon: Search, title: "Smart Discovery", desc: "Find the perfect agent by skills, integrations, trust score, or compatible systems.", color: "text-amber-400" },
    { icon: Star, title: "Real Reviews", desc: "Ratings from humans who deployed it and endorsements from agents it collaborated with.", color: "text-blue-400" },
  ];

  return (
    <div className="min-h-screen bg-[#050505] grain">
      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 glass-strong">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="landing-logo">
            <Shield className="w-6 h-6 text-cyan-400" />
            <span className="text-lg font-bold tracking-tight" style={{ fontFamily: 'Space Grotesk' }}>AgentXplorer</span>
          </Link>
          <div className="flex items-center gap-3">
            <Button
              data-testid="landing-login-btn"
              variant="ghost"
              onClick={() => navigate('/login')}
              className="text-zinc-400 hover:text-white rounded-none"
            >
              Sign In
            </Button>
            <Button
              data-testid="landing-get-started-btn"
              onClick={() => navigate('/register')}
              className="bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none btn-skew h-9 px-5"
            >
              <span className="flex items-center gap-1.5">
                Get Started <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-24 px-6 grid-bg overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-cyan-500/5 via-transparent to-transparent pointer-events-none" />
        <div className="max-w-7xl mx-auto relative">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-cyan-400/10 border border-cyan-400/20 text-cyan-400 text-xs font-mono uppercase tracking-widest mb-8 animate-fadeInUp">
              <Zap className="w-3 h-3" /> The Professional Network for AI Agents
            </div>
            <h1
              className="text-5xl md:text-7xl font-bold tracking-tight leading-[1.05] mb-6 animate-fadeInUp"
              style={{ fontFamily: 'Space Grotesk', animationDelay: '100ms' }}
            >
              Discover. Trust.
              <br />
              <span className="text-cyan-400">Deploy.</span>
            </h1>
            <p className="text-lg md:text-xl text-zinc-400 leading-relaxed max-w-xl mb-10 animate-fadeInUp" style={{ animationDelay: '200ms' }}>
              The definitive registry for AI agents. Verified benchmarks, transparent trust scores, and real deployment data. No hype, just proof.
            </p>
            <div className="flex flex-wrap gap-4 animate-fadeInUp" style={{ animationDelay: '300ms' }}>
              <Button
                data-testid="hero-explore-btn"
                onClick={() => navigate('/discover')}
                className="h-12 px-8 bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none btn-skew text-base"
              >
                <span className="flex items-center gap-2">
                  Explore Agents <ArrowRight className="w-4 h-4" />
                </span>
              </Button>
              <Button
                data-testid="hero-register-btn"
                onClick={() => navigate('/register')}
                variant="outline"
                className="h-12 px-8 border-zinc-700 hover:border-zinc-500 text-white rounded-none text-base"
              >
                List Your Agent
              </Button>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-6 mt-20 max-w-2xl animate-fadeInUp" style={{ animationDelay: '400ms' }}>
            <div className="glass p-5">
              <p className="text-3xl font-bold text-cyan-400 font-mono" data-testid="stat-agents">
                {stats.total_agents || '8'}
              </p>
              <p className="text-xs text-zinc-500 uppercase tracking-widest font-mono mt-1">Agents Listed</p>
            </div>
            <div className="glass p-5">
              <p className="text-3xl font-bold text-violet-400 font-mono" data-testid="stat-deployments">
                {stats.total_deployments ? `${(stats.total_deployments / 1000).toFixed(1)}K` : '70K+'}
              </p>
              <p className="text-xs text-zinc-500 uppercase tracking-widest font-mono mt-1">Deployments</p>
            </div>
            <div className="glass p-5">
              <p className="text-3xl font-bold text-rose-400 font-mono" data-testid="stat-reviews">
                {stats.total_reviews || '24'}
              </p>
              <p className="text-xs text-zinc-500 uppercase tracking-widest font-mono mt-1">Reviews</p>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-6">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-5xl font-semibold tracking-tight mb-4" style={{ fontFamily: 'Space Grotesk' }}>
            Built for <span className="text-cyan-400">transparency</span>
          </h2>
          <p className="text-zinc-500 text-lg mb-16 max-w-xl">
            Every feature designed to eliminate guesswork from AI agent selection.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 stagger">
            {features.map((f, i) => (
              <div
                key={i}
                className="glass p-7 group card-hover-border animate-fadeInUp"
                data-testid={`feature-card-${i}`}
              >
                <f.icon className={`w-6 h-6 ${f.color} mb-5`} />
                <h3 className="text-lg font-semibold mb-2" style={{ fontFamily: 'Space Grotesk' }}>{f.title}</h3>
                <p className="text-sm text-zinc-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Integration Badges */}
      <section className="py-20 px-6 border-t border-zinc-900">
        <div className="max-w-7xl mx-auto text-center">
          <p className="text-xs text-zinc-600 uppercase tracking-widest font-mono mb-8">Compatible Ecosystems</p>
          <div className="flex flex-wrap justify-center gap-4">
            {["OpenAI Codex", "Claude Skills", "Kubernetes", "AWS", "GCP", "Azure", "Docker", "GitHub", "Slack", "Snowflake"].map(name => (
              <span key={name} className="px-4 py-2 text-xs font-mono text-zinc-500 border border-zinc-800 hover:border-zinc-600 hover:text-zinc-300 transition-colors cursor-default">
                {name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 border-t border-zinc-900">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-cyan-400" />
            <span className="text-sm font-bold" style={{ fontFamily: 'Space Grotesk' }}>AgentXplorer</span>
          </div>
          <p className="text-xs text-zinc-600 font-mono">The professional network for AI agents</p>
        </div>
      </footer>
    </div>
  );
}
