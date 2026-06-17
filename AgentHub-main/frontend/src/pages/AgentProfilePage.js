import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { agentAPI, reviewAPI } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { TrustScoreRing, TrustBreakdown } from "@/components/TrustScore";
import { VerifiedBadge } from "@/components/VerifiedBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Star, TrendingUp, Clock, AlertTriangle, CheckCircle, ExternalLink, ArrowUpRight,
  Shield, Zap, GitBranch, MessageSquare, ThumbsUp, AlertCircle, Sparkles, Github, GitFork, Scale, Box, Download, Heart
} from "lucide-react";
import { toast } from "sonner";

export default function AgentProfilePage() {
  const { agentId } = useParams();
  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [showReview, setShowReview] = useState(false);
  const [reviewForm, setReviewForm] = useState({ rating: 5, comment: "" });
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchAgent = async () => {
      try {
        const resp = await agentAPI.get(agentId);
        setAgent(resp.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchAgent();
  }, [agentId]);

  const handleReview = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await reviewAPI.create({ agent_id: agentId, ...reviewForm });
      toast.success("Review submitted");
      setShowReview(false);
      setReviewForm({ rating: 5, comment: "" });
      const resp = await agentAPI.get(agentId);
      setAgent(resp.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505]">
        <Navbar />
        <div className="pt-24 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="min-h-screen bg-[#050505]">
        <Navbar />
        <div className="pt-24 text-center">
          <p className="text-zinc-500 text-lg">Agent not found</p>
          <Button onClick={() => navigate('/discover')} className="mt-4 bg-cyan-400 text-black rounded-none">Back to Discover</Button>
        </div>
      </div>
    );
  }

  const avgRating = agent.reviews?.length > 0 ? (agent.reviews.reduce((a, r) => a + r.rating, 0) / agent.reviews.length).toFixed(1) : "N/A";

  return (
    <div className="min-h-screen bg-[#050505]">
      <Navbar />
      <main className="pt-20 pb-16 px-6">
        <div className="max-w-7xl mx-auto">

          {/* Hero Section */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-10">
            {/* Main Info - spans 3 cols */}
            <div className="lg:col-span-3 glass p-8 animate-fadeInUp">
              <div className="flex flex-col md:flex-row md:items-start gap-6">
                {agent.avatar_url ? (
                  <img src={agent.avatar_url} alt={agent.name} className="w-20 h-20 rounded-full object-cover border-2 border-zinc-800 flex-shrink-0" />
                ) : (
                  <div className="w-20 h-20 rounded-full bg-zinc-800 flex items-center justify-center text-cyan-400 font-bold text-3xl flex-shrink-0">{agent.name?.[0]}</div>
                )}
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-3 mb-2">
                    <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ fontFamily: 'Space Grotesk' }} data-testid="agent-name">
                      {agent.name}
                    </h1>
                    <Badge className="bg-cyan-400/10 text-cyan-400 border-cyan-400/20 font-mono text-xs rounded-sm capitalize">{agent.category}</Badge>
                    <VerifiedBadge isVerified={agent.is_verified} />
                  </div>
                  <p className="text-sm text-zinc-500 font-mono mb-3" data-testid="agent-builder">Built by {agent.builder}</p>
                  <p className="text-zinc-400 leading-relaxed mb-5">{agent.description}</p>
                  {agent.demo_url && (
                    <div className="mb-5">
                      <a
                        href={agent.demo_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 text-sm font-mono font-bold px-4 py-2 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 hover:bg-cyan-400/20 hover:border-cyan-400/50 hover:text-cyan-300 transition-all"
                        data-testid="agent-demo-link"
                      >
                        <Zap className="w-4 h-4" /> Try Now
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  )}

                  {/* Integration badges */}
                  <div className="flex flex-wrap gap-2">
                    {agent.source === "github" && (
                      <Badge className="bg-zinc-800 text-zinc-300 border-zinc-700 font-mono text-xs rounded-sm">
                        <Github className="w-3 h-3 mr-1" /> GitHub
                      </Badge>
                    )}
                    {agent.source === "huggingface" && (
                      <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/20 font-mono text-xs rounded-sm">
                        <Box className="w-3 h-3 mr-1" /> HuggingFace
                      </Badge>
                    )}
                    {agent.integrations?.map(intg => (
                      <Badge key={intg} variant="outline" className={`text-xs font-mono rounded-sm ${
                        intg === 'OpenAI Codex' || intg === 'OpenAI' ? 'badge-codex' : intg === 'Claude Skills' ? 'badge-claude' : 'border-zinc-700 text-zinc-500'
                      }`} data-testid={`integration-badge-${intg.replace(/\s/g,'-')}`}>
                        {intg}
                      </Badge>
                    ))}
                  </div>

                  {/* GitHub-specific info */}
                  {agent.source === "github" && (
                    <div className="flex flex-wrap items-center gap-4 mt-4 pt-3 border-t border-zinc-800/30">
                      <div className="flex items-center gap-1.5 text-sm">
                        <Star className="w-4 h-4 text-amber-400" />
                        <span className="font-mono text-amber-400 font-bold">{agent.github_stars?.toLocaleString()}</span>
                        <span className="text-zinc-600 text-xs">stars</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-sm text-zinc-400">
                        <GitFork className="w-4 h-4" />
                        <span className="font-mono">{agent.github_forks?.toLocaleString()}</span>
                        <span className="text-zinc-600 text-xs">forks</span>
                      </div>
                      {agent.github_language && (
                        <div className="flex items-center gap-1.5 text-sm text-zinc-400">
                          <span className="w-2.5 h-2.5 rounded-full bg-violet-400" />
                          <span className="font-mono">{agent.github_language}</span>
                        </div>
                      )}
                      {agent.github_license && (
                        <div className="flex items-center gap-1.5 text-sm text-zinc-400">
                          <Scale className="w-4 h-4" />
                          <span className="font-mono">{agent.github_license}</span>
                        </div>
                      )}
                      {agent.github_url && (
                        <a
                          href={agent.github_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-auto inline-flex items-center gap-2 text-sm font-mono font-bold px-4 py-2 bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 hover:bg-cyan-400/20 hover:border-cyan-400/50 hover:text-cyan-300 transition-all"
                          data-testid="github-repo-link"
                        >
                          <Github className="w-4 h-4" /> View Repository
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  )}

                  {/* HuggingFace-specific info */}
                  {agent.source === "huggingface" && (
                    <div className="flex flex-wrap items-center gap-4 mt-4 pt-3 border-t border-zinc-800/30">
                      <div className="flex items-center gap-1.5 text-sm">
                        <Download className="w-4 h-4 text-cyan-400" />
                        <span className="font-mono text-cyan-400 font-bold">{agent.hf_downloads?.toLocaleString()}</span>
                        <span className="text-zinc-600 text-xs">downloads</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-sm text-rose-400">
                        <Heart className="w-4 h-4" />
                        <span className="font-mono font-bold">{agent.hf_likes?.toLocaleString()}</span>
                        <span className="text-zinc-600 text-xs">likes</span>
                      </div>
                      {agent.hf_pipeline_tag && (
                        <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/20 text-xs font-mono rounded-sm">
                          {agent.hf_pipeline_tag}
                        </Badge>
                      )}
                      {agent.hf_url && (
                        <a
                          href={agent.hf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-auto inline-flex items-center gap-2 text-sm font-mono font-bold px-4 py-2 bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 hover:border-amber-500/50 hover:text-amber-300 transition-all"
                          data-testid="hf-model-link"
                        >
                          <Box className="w-4 h-4" /> View on HuggingFace
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Stats Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 pt-6 border-t border-zinc-800/50">
                <div>
                  <p className="text-2xl font-bold font-mono text-cyan-400" data-testid="deployment-count">{agent.deployment_count?.toLocaleString()}</p>
                  <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono mt-0.5">{agent.source === "github" ? "Stars" : agent.source === "huggingface" ? "Downloads" : "Deployments"}</p>
                </div>
                {agent.source === "github" ? (
                  <div>
                    <p className="text-2xl font-bold font-mono text-violet-400">{agent.github_forks?.toLocaleString()}</p>
                    <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono mt-0.5">Forks</p>
                  </div>
                ) : agent.source === "huggingface" ? (
                  <div>
                    <p className="text-2xl font-bold font-mono text-rose-400">{agent.hf_likes?.toLocaleString()}</p>
                    <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono mt-0.5">Likes</p>
                  </div>
                ) : (
                  <div>
                    <p className="text-2xl font-bold font-mono text-emerald-400" data-testid="uptime-value">{agent.uptime}%</p>
                    <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono mt-0.5">Uptime</p>
                  </div>
                )}
                <div>
                  <p className="text-2xl font-bold font-mono text-red-400" data-testid="error-rate-value">{agent.error_rate}%</p>
                  <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono mt-0.5">Error Rate</p>
                </div>
                <div>
                  <p className="text-2xl font-bold font-mono text-amber-400">{avgRating}</p>
                  <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono mt-0.5">Avg Rating</p>
                </div>
              </div>
            </div>

            {/* Trust Score - 1 col */}
            <div className="glass p-6 flex flex-col items-center justify-center animate-fadeInUp" style={{ animationDelay: '100ms' }}>
              <TrustScoreRing score={agent.trust_score} size={160} />
              <div className="w-full mt-6">
                <TrustBreakdown breakdown={agent.trust_breakdown} />
              </div>
            </div>
          </div>

          {/* AI Summary */}
          {agent.auto_summary && (
            <div className="glass p-6 mb-6 animate-fadeInUp border-l-2 border-violet-500/50" data-testid="ai-summary">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="w-4 h-4 text-violet-400" />
                <span className="text-xs text-violet-400 uppercase tracking-widest font-mono">AI-Generated Summary (GPT-5.2)</span>
              </div>
              <p className="text-sm text-zinc-400 leading-relaxed">{agent.auto_summary}</p>
            </div>
          )}

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="animate-fadeInUp" style={{ animationDelay: '200ms' }}>
            <TabsList className="bg-zinc-900/50 border border-zinc-800 rounded-none p-1 h-auto">
              <TabsTrigger value="overview" className="rounded-none text-sm data-[state=active]:bg-cyan-400/10 data-[state=active]:text-cyan-400" data-testid="tab-overview">
                Skills & Benchmarks
              </TabsTrigger>
              <TabsTrigger value="portfolio" className="rounded-none text-sm data-[state=active]:bg-cyan-400/10 data-[state=active]:text-cyan-400" data-testid="tab-portfolio">
                Portfolio ({agent.portfolio?.length || 0})
              </TabsTrigger>
              <TabsTrigger value="reviews" className="rounded-none text-sm data-[state=active]:bg-cyan-400/10 data-[state=active]:text-cyan-400" data-testid="tab-reviews">
                Reviews ({agent.reviews?.length || 0})
              </TabsTrigger>
              <TabsTrigger value="versions" className="rounded-none text-sm data-[state=active]:bg-cyan-400/10 data-[state=active]:text-cyan-400" data-testid="tab-versions">
                Version History
              </TabsTrigger>
              <TabsTrigger value="network" className="rounded-none text-sm data-[state=active]:bg-cyan-400/10 data-[state=active]:text-cyan-400" data-testid="tab-network">
                Network
              </TabsTrigger>
            </TabsList>

            {/* Skills & Benchmarks */}
            <TabsContent value="overview" className="mt-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Skills */}
                <div className="glass p-6">
                  <h3 className="text-lg font-semibold mb-5" style={{ fontFamily: 'Space Grotesk' }}>Verified Skills</h3>
                  <div className="space-y-4">
                    {agent.skills?.map((skill, i) => (
                      <div key={i} data-testid={`skill-${skill.name.replace(/\s/g,'-')}`}>
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-zinc-300">{skill.name}</span>
                            {skill.verified && (
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger>
                                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                                  </TooltipTrigger>
                                  <TooltipContent className="bg-zinc-900 border-zinc-800 text-xs">
                                    Independently verified benchmark
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            )}
                          </div>
                          <span className="text-sm font-bold font-mono text-cyan-400">{skill.benchmark}%</span>
                        </div>
                        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                          <div className="h-full bg-cyan-400 rounded-full transition-all duration-700" style={{ width: `${skill.benchmark}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Compatible Systems */}
                <div className="glass p-6">
                  <h3 className="text-lg font-semibold mb-5" style={{ fontFamily: 'Space Grotesk' }}>Compatible Systems</h3>
                  <div className="flex flex-wrap gap-2">
                    {agent.compatible_systems?.map(sys => (
                      <span key={sys} className="inline-flex items-center gap-1.5 text-xs font-mono px-3 py-1.5 bg-zinc-800/50 border border-zinc-700 text-zinc-400">
                        <Zap className="w-3 h-3 text-cyan-400" />
                        {sys}
                      </span>
                    ))}
                  </div>

                  {/* Incidents */}
                  {agent.incidents?.length > 0 && (
                    <div className="mt-8">
                      <h4 className="text-sm font-semibold text-zinc-400 uppercase tracking-widest font-mono mb-4 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400" /> Incident History
                      </h4>
                      <div className="space-y-3">
                        {agent.incidents.map((inc, i) => (
                          <div key={i} className={`p-3 border-l-2 ${inc.resolved ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-amber-500/50 bg-amber-500/5'}`} data-testid={`incident-${i}`}>
                            <div className="flex items-center gap-2 mb-1">
                              {inc.resolved ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> : <AlertCircle className="w-3.5 h-3.5 text-amber-400" />}
                              <span className="text-sm font-medium">{inc.title}</span>
                              <Badge variant="outline" className={`text-[10px] rounded-sm ml-auto ${
                                inc.severity === 'high' ? 'border-red-500/30 text-red-400' : inc.severity === 'medium' ? 'border-amber-500/30 text-amber-400' : 'border-zinc-700 text-zinc-500'
                              }`}>
                                {inc.severity}
                              </Badge>
                            </div>
                            <p className="text-xs text-zinc-500">{inc.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            {/* Portfolio */}
            <TabsContent value="portfolio" className="mt-6">
              {agent.portfolio?.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {agent.portfolio.map((item, i) => (
                    <div key={i} className="glass overflow-hidden card-hover-border" data-testid={`portfolio-${i}`}>
                      {item.screenshot_url && (
                        <div className="h-48 overflow-hidden">
                          <img src={item.screenshot_url} alt={item.title} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                        </div>
                      )}
                      <div className="p-6">
                        <h3 className="text-lg font-semibold mb-2" style={{ fontFamily: 'Space Grotesk' }}>{item.title}</h3>
                        <p className="text-sm text-zinc-500 mb-4">{item.description}</p>
                        {item.case_study && (
                          <div className="p-3 bg-zinc-900/50 border-l-2 border-cyan-400/30 mb-4">
                            <p className="text-xs text-zinc-400 leading-relaxed">{item.case_study}</p>
                          </div>
                        )}
                        {item.metrics_before && item.metrics_after && (
                          <div className="grid grid-cols-2 gap-3">
                            <div className="p-3 bg-red-500/5 border border-red-500/10">
                              <p className="text-[10px] text-red-400 uppercase tracking-widest font-mono mb-2">Before</p>
                              {Object.entries(item.metrics_before).map(([k, v]) => (
                                <div key={k} className="flex justify-between text-xs mb-1">
                                  <span className="text-zinc-500 capitalize">{k.replace(/_/g, ' ')}</span>
                                  <span className="font-mono text-red-400">{v}</span>
                                </div>
                              ))}
                            </div>
                            <div className="p-3 bg-emerald-500/5 border border-emerald-500/10">
                              <p className="text-[10px] text-emerald-400 uppercase tracking-widest font-mono mb-2">After</p>
                              {Object.entries(item.metrics_after).map(([k, v]) => (
                                <div key={k} className="flex justify-between text-xs mb-1">
                                  <span className="text-zinc-500 capitalize">{k.replace(/_/g, ' ')}</span>
                                  <span className="font-mono text-emerald-400">{v}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {item.tags?.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-4">
                            {item.tags.map(t => <Badge key={t} variant="outline" className="text-[10px] font-mono rounded-sm border-zinc-700 text-zinc-500">{t}</Badge>)}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="glass p-12 text-center"><p className="text-zinc-500">No portfolio items yet</p></div>
              )}
            </TabsContent>

            {/* Reviews */}
            <TabsContent value="reviews" className="mt-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold" style={{ fontFamily: 'Space Grotesk' }}>Reviews & Endorsements</h3>
                <Dialog open={showReview} onOpenChange={setShowReview}>
                  <DialogTrigger asChild>
                    <Button className="bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none btn-skew h-9 px-5 text-sm" data-testid="write-review-btn">
                      <span className="flex items-center gap-1.5"><MessageSquare className="w-3.5 h-3.5" /> Write Review</span>
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="bg-[#0a0a0b] border-zinc-800">
                    <DialogHeader>
                      <DialogTitle style={{ fontFamily: 'Space Grotesk' }}>Review {agent.name}</DialogTitle>
                    </DialogHeader>
                    <form onSubmit={handleReview} className="space-y-4 mt-4">
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-widest font-mono mb-2">Rating</p>
                        <div className="flex gap-1">
                          {[1,2,3,4,5].map(n => (
                            <button key={n} type="button" onClick={() => setReviewForm({...reviewForm, rating: n})} data-testid={`rating-star-${n}`}>
                              <Star className={`w-7 h-7 ${n <= reviewForm.rating ? 'text-amber-400 fill-amber-400' : 'text-zinc-700'} transition-colors hover:text-amber-300`} />
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-widest font-mono mb-2">Comment</p>
                        <Textarea
                          data-testid="review-comment"
                          value={reviewForm.comment}
                          onChange={e => setReviewForm({...reviewForm, comment: e.target.value})}
                          className="bg-black/50 border-zinc-800 rounded-none text-white min-h-[100px]"
                          placeholder="Share your experience with this agent..."
                          required
                        />
                      </div>
                      <Button type="submit" disabled={submitting} className="w-full bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none h-10" data-testid="submit-review-btn">
                        {submitting ? "Submitting..." : "Submit Review"}
                      </Button>
                    </form>
                  </DialogContent>
                </Dialog>
              </div>

              {agent.reviews?.length > 0 ? (
                <div className="space-y-4">
                  {agent.reviews.map((review, i) => (
                    <div key={i} className="glass p-5" data-testid={`review-${i}`}>
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                            review.reviewer_type === 'agent' ? 'bg-violet-400/20 text-violet-400' : 'bg-cyan-400/20 text-cyan-400'
                          }`}>
                            {review.reviewer_name?.[0]?.toUpperCase() || "?"}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{review.reviewer_name}</span>
                              <Badge variant="outline" className={`text-[10px] rounded-sm ${
                                review.reviewer_type === 'agent' ? 'badge-claude' : 'border-zinc-700 text-zinc-500'
                              }`}>
                                {review.reviewer_type === 'agent' ? 'Agent' : 'Human'}
                              </Badge>
                            </div>
                            <p className="text-[10px] text-zinc-600 font-mono">{new Date(review.created_at).toLocaleDateString()}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-0.5">
                          {[...Array(5)].map((_, j) => (
                            <Star key={j} className={`w-3.5 h-3.5 ${j < review.rating ? 'text-amber-400 fill-amber-400' : 'text-zinc-700'}`} />
                          ))}
                        </div>
                      </div>
                      <p className="text-sm text-zinc-400 leading-relaxed">{review.comment}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="glass p-12 text-center"><p className="text-zinc-500">No reviews yet. Be the first to review this agent.</p></div>
              )}
            </TabsContent>

            {/* Version History */}
            <TabsContent value="versions" className="mt-6">
              <div className="glass p-6">
                <h3 className="text-lg font-semibold mb-6" style={{ fontFamily: 'Space Grotesk' }}>Version History</h3>
                <div className="space-y-0">
                  {agent.versions?.map((ver, i) => (
                    <div key={i} className="flex gap-4 pb-6 last:pb-0" data-testid={`version-${ver.version}`}>
                      <div className="flex flex-col items-center">
                        <div className="w-3 h-3 rounded-full bg-cyan-400 flex-shrink-0" />
                        {i < agent.versions.length - 1 && <div className="w-px flex-1 bg-zinc-800 mt-1" />}
                      </div>
                      <div className="flex-1 -mt-1">
                        <div className="flex items-center gap-3 mb-1">
                          <span className="text-sm font-bold font-mono text-cyan-400">{ver.version}</span>
                          <span className="text-[10px] text-zinc-600 font-mono">{new Date(ver.date).toLocaleDateString()}</span>
                        </div>
                        <p className="text-sm text-zinc-400">{ver.changelog}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            {/* Network */}
            <TabsContent value="network" className="mt-6">
              <h3 className="text-lg font-semibold mb-6" style={{ fontFamily: 'Space Grotesk' }}>Frequently Deployed With</h3>
              {agent.network?.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {agent.network.map((rec, i) => (
                    <Link key={i} to={`/agents/${rec.agent_id}`} className="glass p-5 card-hover-border group block" data-testid={`network-agent-${rec.agent_id}`}>
                      <div className="flex items-center gap-3 mb-3">
                        {rec.avatar_url ? (
                          <img src={rec.avatar_url} alt="" className="w-10 h-10 rounded-full object-cover border border-zinc-800" />
                        ) : (
                          <div className="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center text-cyan-400 font-bold">{rec.name?.[0]}</div>
                        )}
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-semibold truncate group-hover:text-cyan-400 transition-colors" style={{ fontFamily: 'Space Grotesk' }}>{rec.name}</h4>
                          <p className="text-xs text-zinc-600 font-mono">{rec.builder}</p>
                        </div>
                        <div className="text-right">
                          <span className="text-sm font-bold font-mono text-cyan-400">{rec.trust_score}</span>
                        </div>
                      </div>
                      <p className="text-xs text-zinc-500 line-clamp-2 mb-3">{rec.description}</p>
                      <div className="flex flex-wrap gap-1">
                        {rec.integrations?.slice(0, 3).map(intg => (
                          <span key={intg} className="text-[10px] font-mono text-zinc-600 px-1.5 py-0.5 border border-zinc-800">{intg}</span>
                        ))}
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="glass p-12 text-center"><p className="text-zinc-500">No network recommendations yet</p></div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
}
