import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { agentAPI, authAPI } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Plus, Settings, Sparkles, ExternalLink, TrendingUp, AlertCircle } from "lucide-react";
import { toast } from "sonner";

export default function DashboardPage() {
  const [myAgents, setMyAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [summarizing, setSummarizing] = useState(null);
  const [form, setForm] = useState({ name: "", builder: "", description: "", category: "general", avatar_url: "", demo_url: "", integrations: "", compatible_systems: "" });
  const navigate = useNavigate();

  const fetchMyAgents = useCallback(async () => {
    try {
      const resp = await agentAPI.myAgents();
      setMyAgents(resp.data.agents);
    } catch (err) {
      if (err.response?.status === 401) navigate("/login");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    const verify = async () => {
      try {
        await authAPI.me();
        fetchMyAgents();
      } catch {
        navigate("/login");
      }
    };
    verify();
  }, [fetchMyAgents, navigate]);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const data = {
        ...form,
        integrations: form.integrations.split(",").map(s => s.trim()).filter(Boolean),
        compatible_systems: form.compatible_systems.split(",").map(s => s.trim()).filter(Boolean),
        skills: []
      };
      await agentAPI.create(data);
      toast.success("Agent created successfully");
      setShowCreate(false);
      setForm({ name: "", builder: "", description: "", category: "general", avatar_url: "", demo_url: "", integrations: "", compatible_systems: "" });
      fetchMyAgents();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create agent");
    }
  };

  const handleSummarize = async (agentId) => {
    setSummarizing(agentId);
    try {
      await agentAPI.summarize(agentId);
      toast.success("AI summary generated");
      fetchMyAgents();
    } catch (err) {
      toast.error("Summarization failed. Check your API key balance.");
    } finally {
      setSummarizing(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#050505]">
      <Navbar />
      <main className="pt-20 pb-16 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between mb-10">
            <div>
              <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-2" style={{ fontFamily: 'Space Grotesk' }} data-testid="dashboard-heading">
                Dashboard
              </h1>
              <p className="text-zinc-500">Manage your AI agents</p>
            </div>
            <Dialog open={showCreate} onOpenChange={setShowCreate}>
              <DialogTrigger asChild>
                <Button data-testid="create-agent-btn" className="bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none btn-skew h-10 px-6">
                  <span className="flex items-center gap-2"><Plus className="w-4 h-4" /> List Agent</span>
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#0a0a0b] border-zinc-800 max-w-lg max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle style={{ fontFamily: 'Space Grotesk' }} className="text-xl">Register New Agent</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreate} className="space-y-4 mt-4">
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Agent Name</Label>
                    <Input data-testid="agent-name-input" value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="bg-black/50 border-zinc-800 rounded-none h-10 text-white" required />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Builder / Organization</Label>
                    <Input data-testid="agent-builder-input" value={form.builder} onChange={e => setForm({...form, builder: e.target.value})} className="bg-black/50 border-zinc-800 rounded-none h-10 text-white" required />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Description</Label>
                    <Textarea data-testid="agent-description-input" value={form.description} onChange={e => setForm({...form, description: e.target.value})} className="bg-black/50 border-zinc-800 rounded-none text-white min-h-[80px]" required />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Category</Label>
                    <Select value={form.category} onValueChange={v => setForm({...form, category: v})}>
                      <SelectTrigger data-testid="agent-category-select" className="bg-black/50 border-zinc-800 rounded-none h-10 text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#0a0a0b] border-zinc-800">
                        {["general","coding","data","devops","nlp","vision","automation","security","customer","creative"].map(c => (
                          <SelectItem key={c} value={c} className="text-white capitalize">{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Avatar URL</Label>
                    <Input value={form.avatar_url} onChange={e => setForm({...form, avatar_url: e.target.value})} className="bg-black/50 border-zinc-800 rounded-none h-10 text-white" placeholder="https://..." />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Demo URL (Try Now)</Label>
                    <Input value={form.demo_url} onChange={e => setForm({...form, demo_url: e.target.value})} className="bg-black/50 border-zinc-800 rounded-none h-10 text-white" placeholder="https://..." />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Integrations (comma-separated)</Label>
                    <Input data-testid="agent-integrations-input" value={form.integrations} onChange={e => setForm({...form, integrations: e.target.value})} className="bg-black/50 border-zinc-800 rounded-none h-10 text-white" placeholder="GitHub, Slack, AWS" />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs uppercase tracking-widest font-mono mb-1.5 block">Compatible Systems (comma-separated)</Label>
                    <Input value={form.compatible_systems} onChange={e => setForm({...form, compatible_systems: e.target.value})} className="bg-black/50 border-zinc-800 rounded-none h-10 text-white" placeholder="Docker, Kubernetes, AWS" />
                  </div>
                  <Button data-testid="submit-agent-btn" type="submit" className="w-full bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none h-10">
                    Register Agent
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {[1,2].map(i => <div key={i} className="glass p-6 h-48 animate-pulse"><div className="h-4 w-32 bg-zinc-800 rounded mb-4" /><div className="h-3 w-full bg-zinc-800/50 rounded mb-2" /><div className="h-3 w-2/3 bg-zinc-800/50 rounded" /></div>)}
            </div>
          ) : myAgents.length === 0 ? (
            <div className="glass p-16 text-center">
              <Settings className="w-10 h-10 text-zinc-700 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2" style={{ fontFamily: 'Space Grotesk' }}>No agents yet</h3>
              <p className="text-zinc-500 mb-6">Register your first AI agent to get started</p>
              <Button onClick={() => setShowCreate(true)} className="bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none btn-skew px-6">
                <span className="flex items-center gap-2"><Plus className="w-4 h-4" /> List Your First Agent</span>
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {myAgents.map(agent => (
                <div key={agent.agent_id} className="glass p-6 card-hover-border group" data-testid={`dashboard-agent-${agent.agent_id}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      {agent.avatar_url ? (
                        <img src={agent.avatar_url} alt="" className="w-12 h-12 rounded-full object-cover border border-zinc-800" />
                      ) : (
                        <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center text-cyan-400 font-bold text-lg">{agent.name[0]}</div>
                      )}
                      <div>
                        <h3 className="font-semibold text-lg" style={{ fontFamily: 'Space Grotesk' }}>{agent.name}</h3>
                        <p className="text-xs text-zinc-500 font-mono">{agent.builder}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-cyan-400 font-mono">{agent.trust_score}</div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-widest font-mono">Trust</p>
                    </div>
                  </div>
                  <p className="text-sm text-zinc-400 mb-4 line-clamp-2">{agent.description}</p>
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {agent.integrations?.slice(0, 4).map(i => (
                      <Badge key={i} variant="outline" className={`text-[10px] font-mono rounded-sm ${i === 'OpenAI Codex' ? 'badge-codex' : i === 'Claude Skills' ? 'badge-claude' : 'border-zinc-700 text-zinc-500'}`}>
                        {i}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center gap-3 pt-4 border-t border-zinc-800/50">
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <TrendingUp className="w-3 h-3" />
                      <span className="font-mono">{agent.deployment_count?.toLocaleString()}</span> deploys
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span className="font-mono">{agent.uptime}%</span> uptime
                    </div>
                    <div className="ml-auto flex gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleSummarize(agent.agent_id)}
                        disabled={summarizing === agent.agent_id}
                        className="h-8 text-xs text-violet-400 hover:text-violet-300 hover:bg-violet-400/10"
                        data-testid={`summarize-btn-${agent.agent_id}`}
                      >
                        <Sparkles className="w-3.5 h-3.5 mr-1" />
                        {summarizing === agent.agent_id ? "Generating..." : "AI Summary"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => navigate(`/agents/${agent.agent_id}`)}
                        className="h-8 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10"
                        data-testid={`view-agent-btn-${agent.agent_id}`}
                      >
                        <ExternalLink className="w-3.5 h-3.5 mr-1" /> View
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
