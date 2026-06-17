import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

export const TrustScoreRing = ({ score, size = 140 }) => {
  const color = score >= 90 ? "#10b981" : score >= 80 ? "#22d3ee" : score >= 70 ? "#f59e0b" : "#ef4444";
  const data = [
    { value: score },
    { value: 100 - score }
  ];

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={size * 0.35}
            outerRadius={size * 0.45}
            startAngle={90}
            endAngle={-270}
            dataKey="value"
            stroke="none"
          >
            <Cell fill={color} />
            <Cell fill="#27272a" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold font-mono" style={{ color }}>{score}</span>
        <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Trust</span>
      </div>
    </div>
  );
};

export const TrustBreakdown = ({ breakdown }) => {
  const items = [
    { key: "task_completion", label: "Task Completion", color: "#22d3ee" },
    { key: "security_audit", label: "Security Audit", color: "#8b5cf6" },
    { key: "uptime_score", label: "Uptime Score", color: "#10b981" },
    { key: "user_satisfaction", label: "User Satisfaction", color: "#f43f5e" },
    { key: "repo_health", label: "Repo Health", color: "#f59e0b" },
    { key: "design_quality", label: "Design Quality", color: "#60a5fa" }
  ];

  return (
    <div className="space-y-3">
      {items.map(item => {
        const value = breakdown?.[item.key] || 0;
        return (
          <div key={item.key}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-zinc-500 font-mono uppercase tracking-widest">{item.label}</span>
              <span className="text-xs font-bold font-mono" style={{ color: item.color }}>{value}%</span>
            </div>
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{ width: `${value}%`, backgroundColor: item.color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};
