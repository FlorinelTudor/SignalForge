import { Badge } from "@/components/ui/badge";
import { VerifiedBadge } from "@/components/VerifiedBadge";
import { ArrowUpRight, Download, Heart, ExternalLink, Box } from "lucide-react";

export const HuggingFaceAgentCard = ({ agent, onClick }) => {
  const trustColor = agent.trust_score >= 90 ? "text-emerald-400" : agent.trust_score >= 80 ? "text-cyan-400" : agent.trust_score >= 70 ? "text-amber-400" : "text-red-400";

  const formatDownloads = (n) => {
    if (!n) return "0";
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return n.toString();
  };

  return (
    <div
      onClick={onClick}
      className="glass p-6 cursor-pointer card-hover-border group animate-fadeInUp relative"
      data-testid={`hf-agent-card-${agent.agent_id}`}
    >
      {/* HuggingFace Source Badge */}
      <div className="absolute top-3 right-3">
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-400">
          <Box className="w-2.5 h-2.5" /> HuggingFace
        </span>
      </div>

      {/* Header */}
      <div className="flex items-start gap-4 mb-4">
        <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/20 flex items-center justify-center text-amber-400 font-bold text-lg flex-shrink-0">
          {agent.name?.[0]?.toUpperCase()}
        </div>
        <div className="flex-1 min-w-0 pr-20">
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

      {/* Pipeline tag */}
      {agent.hf_pipeline_tag && (
        <div className="mb-3">
          <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/20 text-[10px] font-mono rounded-sm">
            {agent.hf_pipeline_tag}
          </Badge>
        </div>
      )}

      {/* HuggingFace Stats */}
      <div className="flex flex-wrap gap-4 mb-4">
        <div className="flex items-center gap-1.5 text-xs">
          <Download className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-mono text-cyan-400 font-bold">{formatDownloads(agent.hf_downloads)}</span>
          <span className="text-zinc-600">downloads</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <Heart className="w-3.5 h-3.5 text-rose-400" />
          <span className="font-mono text-rose-400">{agent.hf_likes?.toLocaleString()}</span>
        </div>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {agent.hf_tags?.slice(0, 5).map(tag => (
          <Badge key={tag} variant="outline" className={`text-[10px] font-mono rounded-sm ${
            tag === 'transformers' ? 'border-amber-500/30 text-amber-400' :
            tag === 'pytorch' ? 'border-orange-500/30 text-orange-400' :
            'border-zinc-700 text-zinc-500'
          }`}>
            {tag}
          </Badge>
        ))}
        {agent.hf_tags?.length > 5 && (
          <span className="text-[10px] font-mono text-zinc-600">+{agent.hf_tags.length - 5}</span>
        )}
      </div>

      {agent.demo_url && (
        <div className="flex justify-end mb-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              window.open(agent.demo_url, "_blank", "noopener,noreferrer");
            }}
            className="text-xs font-mono text-cyan-400 hover:text-cyan-300"
          >
            Try Now →
          </button>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-zinc-800/50">
        <div className={`text-sm font-bold font-mono ${trustColor}`}>
          {agent.trust_score} <span className="text-[10px] text-zinc-600 uppercase tracking-widest">Trust</span>
        </div>
        {agent.hf_url && (
          <a
            href={agent.hf_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1.5 text-xs font-mono font-bold px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 hover:text-amber-300 transition-all"
            data-testid={`hf-link-${agent.agent_id}`}
          >
            <ExternalLink className="w-3 h-3" /> View on HuggingFace
          </a>
        )}
      </div>
    </div>
  );
};
