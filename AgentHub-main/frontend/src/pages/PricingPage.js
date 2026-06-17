import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Shield, Sparkles } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { billingAPI, authAPI } from "@/lib/api";

const tiers = [
  {
    name: "Free",
    price: "$0",
    cadence: "",
    description: "Get listed and start building credibility.",
    highlight: false,
    icon: Shield,
    features: [
      "Public profile",
      "Basic listing",
      "Community reviews",
    ],
    cta: "Create Profile",
  },
  {
    name: "Vibe Pro",
    price: "$9",
    cadence: "/mo",
    description: "Fast setup and curated agent packs for vibecoders.",
    highlight: false,
    icon: Sparkles,
    features: [
      "One-click setup",
      "Curated packs",
      "Faster downloads",
      "Vibe Pro quick-starts",
    ],
    cta: "Upgrade to Vibe Pro",
  },
  {
    name: "Verified",
    price: "$49",
    cadence: "/mo",
    description: "Verification, trust report, and priority visibility.",
    highlight: true,
    icon: Sparkles,
    features: [
      "Verified badge",
      "Trust report",
      "Priority placement",
      "Review invite tools",
    ],
    cta: "Get Verified",
  },
  {
    name: "Pro",
    price: "$99",
    cadence: "/mo",
    description: "Growth tools for serious agent builders.",
    highlight: false,
    icon: Sparkles,
    features: [
      "Everything in Verified",
      "Analytics dashboard",
      "Lead capture",
      "Import automation",
    ],
    cta: "Upgrade to Pro",
  },
];

export default function PricingPage() {
  const navigate = useNavigate();
  const [loadingPlan, setLoadingPlan] = useState(null);

  const handleCta = async (tier) => {
    if (tier === "Free") {
      navigate("/register");
      return;
    }
    try {
      await authAPI.me();
    } catch {
      navigate("/login");
      return;
    }
    setLoadingPlan(tier);
    let plan = "pro";
    if (tier === "Verified") plan = "verified";
    if (tier === "Vibe Pro") plan = "vibe";
    billingAPI
      .checkout(plan)
      .then((resp) => {
        window.location.href = resp.data.url;
      })
      .catch(() => {
        setLoadingPlan(null);
      });
  };

  return (
    <div className="min-h-screen bg-[#050505]">
      <Navbar />
      <main className="pt-24 pb-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-3" style={{ fontFamily: "Space Grotesk" }}>
              Pricing for Builders
            </h1>
            <p className="text-zinc-500 text-lg">
              Launch free. Upgrade when you want verified trust and growth.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {tiers.map((tier) => {
              const Icon = tier.icon;
              return (
                <div
                  key={tier.name}
                  className={`glass p-6 border ${tier.highlight ? "border-cyan-400/40" : "border-zinc-800"}`}
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${tier.highlight ? "bg-cyan-400/15 text-cyan-400" : "bg-zinc-800 text-zinc-400"}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm text-zinc-500">{tier.name}</p>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold" style={{ fontFamily: "Space Grotesk" }}>
                          {tier.price}
                        </span>
                        <span className="text-zinc-500 text-sm">{tier.cadence}</span>
                      </div>
                    </div>
                  </div>

                  <p className="text-zinc-500 text-sm mb-5">{tier.description}</p>

                  <ul className="space-y-2 mb-6">
                    {tier.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2 text-sm text-zinc-400">
                        <Check className="w-4 h-4 text-cyan-400 mt-0.5" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    onClick={() => handleCta(tier.name)}
                    className={`${tier.highlight ? "bg-cyan-400 text-black hover:bg-cyan-300" : "bg-zinc-900 text-white hover:bg-zinc-800"} rounded-none w-full h-11 font-bold`}
                    data-testid={`pricing-cta-${tier.name.toLowerCase()}`}
                  >
                    {loadingPlan === tier.name ? "Redirecting..." : tier.cta}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
