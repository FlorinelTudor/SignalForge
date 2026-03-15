import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { agentAPI, metaAPI, syncAPI } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { AgentCard } from "@/components/AgentCard";
import { GitHubAgentCard } from "@/components/GitHubAgentCard";
import { HuggingFaceAgentCard } from "@/components/HuggingFaceAgentCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Search, SlidersHorizontal, Cpu, Code, BarChart3, Server, MessageSquare, Eye, Zap, ShieldCheck, Headphones, Palette, Clock, Github, Box, RefreshCw, CheckCircle } from "lucide-react";
import { githubAPI, huggingfaceAPI } from "@/lib/api";
import { toast } from "sonner";

const CATEGORY_ICONS = {
  general: Cpu, coding: Code, data: BarChart3, devops: Server,
  nlp: MessageSquare, vision: Eye, automation: Zap, security: ShieldCheck,
  customer: Headphones, creative: Palette
};

export default function DiscoverPage() {
  const [agents, setAgents] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [sortBy, setSortBy] = useState("trust_score");
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importingHF, setImportingHF] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const navigate = useNavigate();

  const fetchAgents = useCallback(async () => {
    setLoading(true);
    try {
      const params = { sort_by: sortBy, limit: 50 };
      if (search) params.search = search;
      if (category !== "all") params.category = category;
      if (verifiedOnly) params.verified_only = true;
      const resp = await agentAPI.list(params);
      const nextAgents = Array.isArray(resp?.data?.agents) ? resp.data.agents : [];
      setAgents(nextAgents);
      setTotal(Number(resp?.data?.total) || nextAgents.length || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [search, category, sortBy, verifiedOnly]);

  const fetchGithubAgents = useCallback(async () => {}, []);
  const fetchHfAgents = useCallback(async () => {}, []);

  useEffect(() => {
    fetchAgents();
    syncAPI.status().then(r => setSyncStatus(r.data)).catch(() => {});
  }, [fetchAgents]);

  const handleGitHubImport = async () => {
    setImporting(true);
    setImportResult(null);
    try {
      const resp = await githubAPI.import();
      setImportResult({ ...resp.data, source: "GitHub" });
      toast.success(`Imported ${resp.data.total_imported} agents from GitHub`);
      fetchAgents();
      fetchGithubAgents();
    } catch (err) {
      toast.error("GitHub import failed. Rate limit may have been reached.");
    } finally {
      setImporting(false);
    }
  };

  const handleHFImport = async () => {
    setImportingHF(true);
    setImportResult(null);
    try {
      const resp = await huggingfaceAPI.import();
      setImportResult({ ...resp.data, source: "HuggingFace" });
      toast.success(`Imported ${resp.data.total_imported} agents from HuggingFace`);
      fetchAgents();
      fetchHfAgents();
    } catch (err) {
      toast.error("HuggingFace import failed.");
    } finally {
      setImportingHF(false);
    }
  };

  useEffect(() => {
    metaAPI
      .categories()
      .then(r => setCategories(Array.isArray(r?.data?.categories) ? r.data.categories : []))
      .catch(() => setCategories([]));
  }, []);

  const displayAgents = useMemo(() => (Array.isArray(agents) ? agents : []), [agents]);

  const filteredAgents = useMemo(() => {
    let next = [...displayAgents];
    if (verifiedOnly) {
      next = next.filter((agent) => agent.is_verified);
    }
    const term = search.trim().toLowerCase();
    if (term) {
      next = next.filter((agent) => {
        const name = (agent.name || "").toLowerCase();
        const builder = (agent.builder || "").toLowerCase();
        const desc = (agent.description || "").toLowerCase();
        return name.includes(term) || builder.includes(term) || desc.includes(term);
      });
    }
    if (category !== "all") {
      next = next.filter((agent) => agent.category === category);
    }
    if (sortBy === "name") {
      next.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    } else if (sortBy === "created_at") {
      next.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    } else if (sortBy === "deployment_count") {
      next.sort((a, b) => (b.deployment_count || 0) - (a.deployment_count || 0));
    } else {
      next.sort((a, b) => (b.trust_score || 0) - (a.trust_score || 0));
    }
    return next;
  }, [displayAgents, verifiedOnly, search, category, sortBy]);

  const displayTotal = filteredAgents.length;

  return (
    <div className="min-h-screen bg-[#050505]">
      <Navbar />
      <main className="pt-20 pb-16 px-6">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-10">
            <div>
              <h1
                className="text-4xl sm:text-5xl font-bold tracking-tight mb-3"
                style={{ fontFamily: 'Space Grotesk' }}
                data-testid="discover-heading"
              >
                Discover Agents
              </h1>
              <p className="text-zinc-500 text-lg">
                Browse <span className="text-cyan-400 font-mono">{displayTotal}</span> agents
              </p>
              {syncStatus?.last_sync && (
                <p className="text-[10px] text-zinc-600 font-mono mt-1 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Auto-sync every {syncStatus.sync_interval_hours}h | Last: {new Date(syncStatus.last_sync.timestamp).toLocaleString()}
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                data-testid="github-import-btn"
                onClick={handleGitHubImport}
                disabled={importing}
                className="bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-white rounded-none h-10 px-4 font-mono text-sm"
              >
                {importing ? (
                  <span className="flex items-center gap-2"><RefreshCw className="w-4 h-4 animate-spin" /> Importing...</span>
                ) : (
                  <span className="flex items-center gap-2"><Github className="w-4 h-4" /> GitHub</span>
                )}
              </Button>
              <Button
                data-testid="hf-import-btn"
                onClick={handleHFImport}
                disabled={importingHF}
                className="bg-zinc-900 border border-amber-500/30 hover:border-amber-500/50 text-amber-400 rounded-none h-10 px-4 font-mono text-sm"
              >
                {importingHF ? (
                  <span className="flex items-center gap-2"><RefreshCw className="w-4 h-4 animate-spin" /> Importing...</span>
                ) : (
                  <span className="flex items-center gap-2"><Box className="w-4 h-4" /> HuggingFace</span>
                )}
              </Button>
            </div>
          </div>

          {/* Import Result Banner */}
          {importResult && (
            <div className="glass p-4 mb-6 border-l-2 border-emerald-500/50 animate-fadeInUp" data-testid="import-result">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm text-zinc-300">
                    Fetched <span className="text-emerald-400 font-mono font-bold">{importResult.total_imported}</span> agents from {importResult.source || "GitHub"}
                  </p>
                  {importResult.errors?.length > 0 && (
                    <p className="text-xs text-amber-400/70 mt-1 font-mono">{importResult.errors.length} source(s) had rate-limit or connection issues</p>
                  )}
                </div>
                <button onClick={() => setImportResult(null)} className="text-zinc-600 hover:text-zinc-400 text-sm">Dismiss</button>
              </div>
            </div>
          )}

          {/* Source Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
            <TabsList className="bg-zinc-900/50 border border-zinc-800 rounded-none p-1 h-auto">
              <TabsTrigger value="all" className="rounded-none text-sm data-[state=active]:bg-cyan-400/10 data-[state=active]:text-cyan-400" data-testid="tab-all-agents">
                All Agents <Badge variant="outline" className="ml-1.5 text-[10px] font-mono border-zinc-700 text-zinc-500 rounded-sm">{total}</Badge>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {/* Filters */}
          <div className="flex flex-col md:flex-row gap-4 mb-10">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
              <Input
                data-testid="search-input"
                placeholder="Search agents by name, builder, or skill..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 bg-black/50 border-zinc-800 focus:border-cyan-400 rounded-none h-11 text-white"
              />
            </div>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger data-testid="category-filter" className="w-full md:w-48 bg-black/50 border-zinc-800 rounded-none h-11 text-white">
                <SlidersHorizontal className="w-4 h-4 mr-2 text-zinc-500" />
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent className="bg-[#0a0a0b] border-zinc-800">
                <SelectItem value="all" className="text-white">All Categories</SelectItem>
                {(Array.isArray(categories) ? categories : []).map(c => {
                  const Icon = CATEGORY_ICONS[c.id] || Cpu;
                  return (
                    <SelectItem key={c.id} value={c.id} className="text-white">
                      <span className="flex items-center gap-2"><Icon className="w-3.5 h-3.5" />{c.name}</span>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger data-testid="sort-filter" className="w-full md:w-48 bg-black/50 border-zinc-800 rounded-none h-11 text-white">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent className="bg-[#0a0a0b] border-zinc-800">
                <SelectItem value="trust_score" className="text-white">Trust Score</SelectItem>
                <SelectItem value="deployment_count" className="text-white">Deployments / Stars</SelectItem>
                <SelectItem value="created_at" className="text-white">Newest</SelectItem>
                <SelectItem value="name" className="text-white">Name</SelectItem>
              </SelectContent>
            </Select>
            <div className="flex items-center gap-3 bg-black/50 border border-zinc-800 rounded-none h-11 px-3 text-white w-full md:w-auto">
              <span className="text-xs text-zinc-500 font-mono uppercase tracking-widest">Verified Only</span>
              <Switch checked={verifiedOnly} onCheckedChange={setVerifiedOnly} />
            </div>
          </div>

          {/* Results */}
          {loading && activeTab === "all" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="glass p-6 animate-pulse">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="w-12 h-12 rounded-full bg-zinc-800" />
                    <div className="flex-1">
                      <div className="h-4 w-32 bg-zinc-800 rounded mb-2" />
                      <div className="h-3 w-24 bg-zinc-800/50 rounded" />
                    </div>
                  </div>
                  <div className="h-3 w-full bg-zinc-800/50 rounded mb-2" />
                  <div className="h-3 w-3/4 bg-zinc-800/50 rounded" />
                </div>
              ))}
            </div>
          ) : filteredAgents.length === 0 ? (
            <div className="text-center py-20">
              <>
                <Search className="w-10 h-10 text-zinc-700 mx-auto mb-4" />
                <p className="text-zinc-500 text-lg">No agents found</p>
                <p className="text-zinc-600 text-sm mt-1">Try adjusting your search or filters</p>
              </>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 stagger">
              {filteredAgents.map(agent => (
                agent.source === "github" ? (
                  <GitHubAgentCard key={agent.agent_id} agent={agent} onClick={() => navigate(`/agents/${agent.agent_id}`)} />
                ) : agent.source === "huggingface" ? (
                  <HuggingFaceAgentCard key={agent.agent_id} agent={agent} onClick={() => navigate(`/agents/${agent.agent_id}`)} />
                ) : (
                  <AgentCard key={agent.agent_id} agent={agent} onClick={() => navigate(`/agents/${agent.agent_id}`)} />
                )
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
