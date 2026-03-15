import { useEffect, useState } from "react";
import { Download, Lock, Sparkles } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { authAPI } from "@/lib/api";
import { toast } from "sonner";

const packs = [
  {
    id: "startup",
    name: "Startup Launch Pack",
    description: "Analytics + content + support agents for quick MVP launches.",
    file: "/vibe-packs/agentx-startup-pack.json",
    highlights: ["One-click setup", "Launch-ready content", "Support triage"],
  },
  {
    id: "growth",
    name: "Growth & Ops Pack",
    description: "Automation and reliability workflows for growth teams.",
    file: "/vibe-packs/agentx-growth-pack.json",
    highlights: ["Activation tracking", "Incident alerts", "Ops dashboards"],
  },
  {
    id: "dev",
    name: "Dev Acceleration Pack",
    description: "Code review + docs to ship faster with guardrails.",
    file: "/vibe-packs/agentx-dev-pack.json",
    highlights: ["PR reviews", "Docs polish", "Security linting"],
  },
];

export default function VibePage() {
  const [plan, setPlan] = useState("free");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authAPI
      .me()
      .then((resp) => {
        setPlan(resp?.data?.plan || "free");
      })
      .catch(() => setPlan("free"))
      .finally(() => setLoading(false));
  }, []);

  const canAccess = ["vibe", "pro", "verified"].includes(plan);

  const handleDownload = (pack) => {
    if (!canAccess) {
      toast.error("Vibe Pro required. Upgrade to download packs.");
      return;
    }
    window.location.href = pack.file;
  };

  return (
    <div className="min-h-screen bg-[#050505]">
      <Navbar />
      <main className="pt-24 pb-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-10">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-cyan-400/10 border border-cyan-400/20 text-cyan-400 text-xs font-mono uppercase tracking-widest mb-4">
                <Sparkles className="w-3 h-3" /> Vibe Pro Quick Starts
              </div>
              <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-3" style={{ fontFamily: "Space Grotesk" }}>
                One‑click agent packs
              </h1>
              <p className="text-zinc-500 text-lg">
                Curated bundles to deploy agents fast. No README rabbit holes.
              </p>
            </div>
            <div>
              <Button
                onClick={() => (window.location.href = "/pricing")}
                className="bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none h-11 px-6"
              >
                {canAccess ? "Manage Plan" : "Upgrade to Vibe Pro"}
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {packs.map((pack) => (
              <div key={pack.id} className="glass p-6 border border-zinc-800">
                <h3 className="text-lg font-semibold mb-2" style={{ fontFamily: "Space Grotesk" }}>
                  {pack.name}
                </h3>
                <p className="text-sm text-zinc-500 mb-4">{pack.description}</p>
                <ul className="text-xs text-zinc-400 space-y-1 mb-6">
                  {pack.highlights.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
                <Button
                  disabled={loading}
                  onClick={() => handleDownload(pack)}
                  className="w-full rounded-none h-10 bg-zinc-900 text-white hover:bg-zinc-800"
                >
                  <span className="flex items-center gap-2">
                    {canAccess ? <Download className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
                    {canAccess ? "Download Pack" : "Locked"}
                  </span>
                </Button>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
