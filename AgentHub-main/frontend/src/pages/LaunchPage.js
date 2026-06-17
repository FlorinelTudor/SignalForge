import { useState } from "react";
import { Link } from "react-router-dom";
import { Rocket, Mail, CheckCircle } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export default function LaunchPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;
    try {
      const existing = JSON.parse(localStorage.getItem("newsletter_emails") || "[]");
      const next = Array.from(new Set([...existing, trimmed]));
      localStorage.setItem("newsletter_emails", JSON.stringify(next));
    } catch {}
    setSubmitted(true);
    setEmail("");
    toast.success("Thanks — you’re on the list.");
  };

  return (
    <div className="min-h-screen bg-[#050505]">
      <Navbar />
      <main className="pt-24 pb-20 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="glass p-8 md:p-10">
            <div className="flex items-center gap-3 mb-6 text-cyan-400">
              <Rocket className="w-6 h-6" />
              <span className="text-xs font-mono uppercase tracking-widest">Launch Story</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4" style={{ fontFamily: "Space Grotesk" }}>
              Why we built AgentXplorer
            </h1>
            <p className="text-zinc-400 text-lg mb-6">
              We kept seeing the same problem: hundreds of AI agents, but no easy way to know which ones are real,
              safe, and actively maintained. So we built a directory that adds trust signals and a fast path for vibecoders
              who just want to try things without the setup pain.
            </p>
            <div className="grid md:grid-cols-3 gap-4 mb-8">
              <div className="glass p-4 border border-zinc-800">
                <p className="text-sm text-zinc-400">Verified trust badges</p>
              </div>
              <div className="glass p-4 border border-zinc-800">
                <p className="text-sm text-zinc-400">Clear benchmarks and signals</p>
              </div>
              <div className="glass p-4 border border-zinc-800">
                <p className="text-sm text-zinc-400">Vibe Pro quick‑starts</p>
              </div>
            </div>

            <div className="border-t border-zinc-800/80 pt-6">
              <h2 className="text-xl font-semibold mb-2" style={{ fontFamily: "Space Grotesk" }}>Stay in the loop</h2>
              <p className="text-zinc-500 text-sm mb-4">We’ll send updates when new packs and verification features launch.</p>
              <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3">
                <Input
                  type="email"
                  placeholder="you@domain.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="bg-black/50 border-zinc-800 focus:border-cyan-400 rounded-none h-11 text-white"
                  required
                />
                <Button type="submit" className="bg-cyan-400 text-black font-bold hover:bg-cyan-300 rounded-none h-11 px-6">
                  <span className="flex items-center gap-2">
                    <Mail className="w-4 h-4" /> Join the list
                  </span>
                </Button>
              </form>
              {submitted && (
                <div className="flex items-center gap-2 text-emerald-400 text-sm mt-3">
                  <CheckCircle className="w-4 h-4" /> You’re on the list.
                </div>
              )}
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/pricing">
                <Button className="bg-zinc-900 text-white hover:bg-zinc-800 rounded-none h-10">See Pricing</Button>
              </Link>
              <Link to="/discover">
                <Button variant="outline" className="rounded-none h-10 border-zinc-700 text-white">Explore Agents</Button>
              </Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
