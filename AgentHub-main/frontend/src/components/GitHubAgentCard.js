import { Badge } from "@/components/ui/badge";
import { VerifiedBadge } from "@/components/VerifiedBadge";
import { Star, GitFork, ExternalLink, ArrowUpRight, Github, Scale } from "lucide-react";

export const GitHubAgentCard = ({ agent, onClick }) => {
  const trustColor = agent.trust_score >= 90 ? "text-emerald-400" : agent.trust_score >= 80 ? "text-cyan-400" : agent.trust_score >= 70 ? "text-amber-400" : "text-red-400";

  return (
    <div
      onClick={onClick}
      className="glass p-6 cursor-pointer card-hover-border group animate-fadeInUp relative"
      data-testid={`github-agent-card-${agent.agent_id}`}
    >
      {/* GitHub Source Badge */}
      <div className="absolute top-3 right-3">
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 bg-zinc-800 border border-zinc-700 text-zinc-400">
          <Github className="w-2.5 h-2.5" /> GitHub
        </span>
      </div>

      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        {agent.avatar_url ? (
          <img src={agent.avatar_url} alt={agent.name} className="w-12 h-12 rounded-full object-cover border border-zinc-800 flex-shrink-0" />
        ) : (
          <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center text-cyan-400 font-bold text-lg flex-shrink-0">
            {agent.name?.[0]}
          </div>
        )}
        <div className="flex-1 min-w-0 pr-16">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-base truncate group-hover:text-cyan-400 transition-colors" style={{ fontFamily: 'Space Grotesk' }}>
              {agent.name}
            </h3>
            <VerifiedBadge isVerified={agent.is_verified} />
            <ArrowUpRight className="w-3.5 h-3.5 text-zinc-600 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
          </div>
          <p className="text-xs text-zinc-500 font-mono">{agent.builder}</p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-zinc-500 leading-relaxed mb-4 line-clamp-2">{agent.description}</p>

      {/* GitHub Stats */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-1.5 text-xs">
          <Star className="w-3.5 h-3.5 text-amber-400" />
          <span className="font-mono text-amber-400 font-bold">{agent.github_stars?.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <GitFork className="w-3.5 h-3.5" />
          <span className="font-mono">{agent.github_forks?.toLocaleString()}</span>
        </div>
        {agent.github_language && (
          <div className="flex items-center gap-1.5 text-xs text-zinc-500">
            <span className="w-2 h-2 rounded-full bg-violet-400" />
            <span className="font-mono">{agent.github_language}</span>
          </div>
        )}
        {agent.github_license && (
          <div className="flex items-center gap-1.5 text-xs text-zinc-500">
            <Scale className="w-3 h-3" />
            <span className="font-mono">{agent.github_license}</span>
          </div>
        )}
      </div>

      {/* Topics / Integrations */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {agent.github_topics?.slice(0, 5).map(topic => (
          <Badge key={topic} variant="outline" className={`text-[10px] font-mono rounded-sm ${
            topic.includes('openai') || topic.includes('codex') ? 'badge-codex' :
            topic.includes('claude') || topic.includes('anthropic') ? 'badge-claude' :
            'border-zinc-700 text-zinc-500'
          }`}>
            {topic}
          </Badge>
        ))}
        {agent.github_topics?.length > 5 && (
          <span className="text-[10px] font-mono text-zinc-600">+{agent.github_topics.length - 5}</span>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-zinc-800/50">
        <div className={`text-sm font-bold font-mono ${trustColor}`}>
          {agent.trust_score} <span className="text-[10px] text-zinc-600 uppercase tracking-widest">Trust</span>
        </div>
        <div className="flex items-center gap-2">
          {agent.demo_url && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                window.open(agent.demo_url, "_blank", "noopener,noreferrer");
              }}
              className="text-xs font-mono text-cyan-400 hover:text-cyan-300"
            >
              Try Now →
            </button>
          )}
          {agent.github_url && (
            <a
              href={agent.github_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1.5 text-xs font-mono font-bold px-3 py-1.5 bg-cyan-400/10 border border-cyan-400/20 text-cyan-400 hover:bg-cyan-400/20 hover:text-cyan-300 transition-all"
              data-testid={`github-link-${agent.agent_id}`}
            >
              <Github className="w-3 h-3" /> View Repository
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
