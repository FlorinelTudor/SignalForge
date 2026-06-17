import { Badge } from "@/components/ui/badge";
import { VerifiedBadge } from "@/components/VerifiedBadge";
import { Star, TrendingUp, ArrowUpRight } from "lucide-react";

export const AgentCard = ({ agent, onClick }) => {
  const trustColor = agent.trust_score >= 90 ? "text-emerald-400" : agent.trust_score >= 80 ? "text-cyan-400" : agent.trust_score >= 70 ? "text-amber-400" : "text-red-400";

  return (
    <div
      onClick={onClick}
      className="glass p-6 cursor-pointer card-hover-border group animate-fadeInUp"
      data-testid={`agent-card-${agent.agent_id}`}
    >
      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        {agent.avatar_url ? (
          <img src={agent.avatar_url} alt={agent.name} className="w-12 h-12 rounded-full object-cover border border-zinc-800 flex-shrink-0" />
        ) : (
          <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center text-cyan-400 font-bold text-lg flex-shrink-0">
            {agent.name?.[0]}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-base truncate group-hover:text-cyan-400 transition-colors" style={{ fontFamily: 'Space Grotesk' }}>
              {agent.name}
            </h3>
            <VerifiedBadge isVerified={agent.is_verified} />
            <ArrowUpRight className="w-3.5 h-3.5 text-zinc-600 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
          </div>
          <p className="text-xs text-zinc-500 font-mono">{agent.builder}</p>
        </div>
        <div className="text-right flex-shrink-0">
          <div className={`text-xl font-bold font-mono ${trustColor}`} data-testid={`trust-score-${agent.agent_id}`}>
            {agent.trust_score}
          </div>
          <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono">Trust</p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-zinc-500 leading-relaxed mb-4 line-clamp-2">{agent.description}</p>

      {/* Skills */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {agent.skills?.slice(0, 3).map((s, i) => (
          <span key={i} className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 bg-cyan-400/5 border border-cyan-400/10 text-cyan-400/80">
            {s.name}
            {s.verified && <Star className="w-2.5 h-2.5 fill-current" />}
            <span className="text-cyan-400/50">{s.benchmark}%</span>
          </span>
        ))}
        {agent.skills?.length > 3 && (
          <span className="text-[10px] font-mono text-zinc-600 px-2 py-0.5">+{agent.skills.length - 3}</span>
        )}
      </div>

      {/* Integrations */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {agent.integrations?.slice(0, 3).map(intg => (
          <Badge key={intg} variant="outline" className={`text-[10px] font-mono rounded-sm ${
            intg === 'OpenAI Codex' ? 'badge-codex' : intg === 'Claude Skills' ? 'badge-claude' : 'border-zinc-700 text-zinc-500'
          }`}>
            {intg}
          </Badge>
        ))}
        {agent.integrations?.length > 3 && (
          <span className="text-[10px] font-mono text-zinc-600">+{agent.integrations.length - 3}</span>
        )}
      </div>

      {/* Footer Stats */}
      <div className="flex items-center gap-4 pt-3 border-t border-zinc-800/50">
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <TrendingUp className="w-3 h-3" />
          <span className="font-mono">{agent.deployment_count?.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span className="font-mono">{agent.uptime}%</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
          <span className="font-mono">{agent.error_rate}%</span> err
        </div>
        {agent.demo_url && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              window.open(agent.demo_url, "_blank", "noopener,noreferrer");
            }}
            className="ml-auto text-xs font-mono text-cyan-400 hover:text-cyan-300"
          >
            Try Now →
          </button>
        )}
      </div>
    </div>
  );
};
