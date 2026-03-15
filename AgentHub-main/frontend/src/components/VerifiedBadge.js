import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export const VerifiedBadge = ({ isVerified }) => {
  const Icon = isVerified ? ShieldCheck : ShieldAlert;
  const label = isVerified ? "Verified" : "Unverified";
  const classes = isVerified
    ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
    : "bg-zinc-800 text-zinc-400 border-zinc-700";

  return (
    <Badge className={`${classes} font-mono text-[10px] rounded-sm`}>
      <Icon className="w-3 h-3 mr-1" /> {label}
    </Badge>
  );
};
