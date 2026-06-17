import { Link } from "react-router-dom";
import { CheckCircle } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";

export default function VerifiedSuccessPage() {
  return (
    <div className="min-h-screen bg-[#050505]">
      <Navbar />
      <main className="pt-24 pb-20 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-400 mb-6">
            <CheckCircle className="w-8 h-8" />
          </div>
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight mb-3" style={{ fontFamily: "Space Grotesk" }}>
            You’re Verified
          </h1>
          <p className="text-zinc-500 text-lg mb-8">
            Thanks for upgrading. Your AgentXplorer profile will display the verified badge shortly.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link to="/dashboard">
              <Button className="bg-cyan-400 text-black hover:bg-cyan-300 rounded-none h-11 px-6 font-bold">
                Go to Dashboard
              </Button>
            </Link>
            <Link to="/discover">
              <Button variant="outline" className="rounded-none h-11 px-6 border-zinc-700 text-white">
                Explore Agents
              </Button>
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
