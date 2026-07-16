import React, { useState, useEffect } from "react";
import { ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line, Legend } from "recharts";
import { DollarSign, Percent, AlertOctagon, Activity, Landmark, MapPin, ShieldAlert, ArrowUpRight } from "lucide-react";
import { Tenant } from "../types.js";

interface ManagerDashboardProps {
  onSelectAlert?: (caseId: string) => void;
}

export default function ManagerDashboard({ onSelectAlert }: ManagerDashboardProps) {
  const [summary, setSummary] = useState<any>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>("all");
  const [tenantStats, setTenantStats] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        // Fetch summary
        const resSum = await fetch("/api/cases/stats/summary");
        if (resSum.ok) {
          setSummary(await resSum.json());
        }

        // Fetch tenants
        const resTenants = await fetch("/api/tenants");
        if (resTenants.ok) {
          setTenants(await resTenants.json());
        }
      } catch (err) {
        console.error("Failed to load dashboard statistics:", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, []);

  useEffect(() => {
    if (selectedTenantId === "all") {
      setTenantStats(null);
      return;
    }
    async function loadTenantStats() {
      try {
        const res = await fetch(`/api/tenants/${selectedTenantId}/stats`);
        if (res.ok) {
          setTenantStats(await res.json());
        }
      } catch (err) {
        console.error("Failed to load tenant stats:", err);
      }
    }
    loadTenantStats();
  }, [selectedTenantId]);

  if (isLoading || !summary) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-10 font-mono text-xs text-zinc-500">
        <Activity className="w-8 h-8 text-emerald-400 animate-spin mb-3" />
        <span>Loading general swarm analytics...</span>
      </div>
    );
  }

  const { kpis, verdictDistribution, patternDistribution, trendData } = summary;

  // Custom tooltips
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-zinc-950 border border-zinc-800 p-2.5 rounded shadow-xl font-mono text-[10px]">
          <p className="text-zinc-400 mb-1">{label}</p>
          {payload.map((p: any, idx: number) => (
            <p key={idx} style={{ color: p.color || p.fill }} className="font-bold">
              {p.name}: {p.value}
            </p>
          ))}
        </div>
      );
    };
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Top filter select */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
        <div>
          <h2 className="text-sm font-mono font-bold text-zinc-200 uppercase tracking-wider">EXECUTIVE DASHBOARD AND KPIs</h2>
          <p className="text-xs text-zinc-400 mt-0.5">Unified interbank statistics for LATAM Compliance.</p>
        </div>
        <div className="flex items-center gap-2">
          <Landmark className="w-4 h-4 text-zinc-500" />
          <select
            value={selectedTenantId}
            onChange={(e) => setSelectedTenantId(e.target.value)}
            className="bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-300 rounded-lg p-2 focus:outline-none focus:border-emerald-500/50 cursor-pointer"
          >
            <option value="all">ALL BANKS (CONSOLIDATED)</option>
            {tenants.map(t => (
              <option key={t.id} value={t.id}>{t.name} ({t.country})</option>
            ))}
          </select>
        </div>
      </div>

      {/* KPI Stats Strip */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1 */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4.5 flex items-center justify-between shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
          <div className="space-y-1">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block">Estimated Alert Amount</span>
            <span className="text-xl font-mono font-extrabold text-zinc-100 block">
              USD {(kpis.totalAmountsUSD).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
            <span className="text-[9px] font-mono text-emerald-400 flex items-center gap-0.5">
              <ArrowUpRight className="w-3 h-3" /> +14.2% this week
            </span>
          </div>
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-850 text-emerald-400 group-hover:scale-115 transition">
            <DollarSign className="w-5 h-5" />
          </div>
          <div className="absolute right-0 bottom-0 w-24 h-24 bg-emerald-500/2 rounded-full blur-2xl pointer-events-none" />
        </div>

        {/* KPI 2 */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4.5 flex items-center justify-between shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
          <div className="space-y-1">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block">Average Swarm Risk</span>
            <span className="text-xl font-mono font-extrabold text-zinc-100 block">
              {Math.round(kpis.averageRiskScore * 100)}%
            </span>
            <span className="text-[9px] font-mono text-rose-400 flex items-center gap-0.5">
              Average alert severity
            </span>
          </div>
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-850 text-rose-400 group-hover:scale-115 transition">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div className="absolute right-0 bottom-0 w-24 h-24 bg-rose-500/2 rounded-full blur-2xl pointer-events-none" />
        </div>

        {/* KPI 3 */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4.5 flex items-center justify-between shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
          <div className="space-y-1">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block">Global Confidence Interval</span>
            <span className="text-xl font-mono font-extrabold text-zinc-100 block">
              {Math.round(kpis.averageConfidence * 100)}%
            </span>
            <span className="text-[9px] font-mono text-emerald-400">
              Agent Precision V2
            </span>
          </div>
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-850 text-amber-400 group-hover:scale-115 transition">
            <Percent className="w-5 h-5" />
          </div>
          <div className="absolute right-0 bottom-0 w-24 h-24 bg-amber-500/2 rounded-full blur-2xl pointer-events-none" />
        </div>

        {/* KPI 4 */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4.5 flex items-center justify-between shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
          <div className="space-y-1">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block">Evaluated Cases (24h)</span>
            <span className="text-xl font-mono font-extrabold text-zinc-100 block">
              {kpis.alertsProcessedLast24h}
            </span>
            <span className="text-[9px] font-mono text-zinc-400">
              Average response SLA &lt;15s
            </span>
          </div>
          <div className="p-3 bg-zinc-950 rounded-lg border border-zinc-850 text-sky-400 group-hover:scale-115 transition">
            <Activity className="w-5 h-5" />
          </div>
          <div className="absolute right-0 bottom-0 w-24 h-24 bg-sky-500/2 rounded-full blur-2xl pointer-events-none" />
        </div>
      </div>

      {/* If specific bank is selected, show its customized metrics first */}
      {tenantStats && (
        <div className="bg-emerald-500/5 border border-emerald-500/25 p-4 rounded-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Landmark className="w-6 h-6 text-emerald-400" />
            <div>
              <h3 className="text-xs font-mono font-bold text-emerald-300 uppercase">Tenant Specific Metrics</h3>
              <p className="text-xs text-zinc-300 mt-0.5">
                Total Alerts: <span className="font-mono font-bold text-zinc-100">{tenantStats.totalAlerts}</span> | 
                Critical (Risk &gt; 0.8): <span className="font-mono font-bold text-rose-400">{tenantStats.criticalAlerts}</span> |
                Average Bank Risk: <span className="font-mono font-bold text-zinc-100">{Math.round(tenantStats.averageRiskScore * 100)}%</span>
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {tenantStats.distribution.map((d: any, idx: number) => (
              <span key={idx} className="text-[9px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                {d.name}: {d.value}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recharts Layout (Donut & Pattern Distributions) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Verdict Distribution Donut */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 flex flex-col h-80">
          <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider mb-2">Verdict Distribution</span>
          <div className="flex-1 relative flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={verdictDistribution}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {verdictDistribution.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            
            {/* Inner text */}
            <div className="absolute text-center">
              <span className="text-2xl font-mono font-extrabold text-zinc-100 block">
                {verdictDistribution.reduce((acc: number, val: any) => acc + val.value, 0)}
              </span>
              <span className="text-[9px] font-mono text-zinc-500 uppercase">Total Alerts</span>
            </div>
          </div>
          {/* Legend items */}
          <div className="flex justify-center gap-3 mt-2 text-[9px] font-mono">
            {verdictDistribution.map((entry: any, idx: number) => (
              <div key={idx} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: entry.color }} />
                <span className="text-zinc-400 uppercase">{entry.name} ({entry.value})</span>
              </div>
            ))}
          </div>
        </div>

        {/* Fraud Pattern distribution Bar chart */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 flex flex-col h-80 lg:col-span-2">
          <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider mb-3">Typological Models & Patterns</span>
          <div className="flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={patternDistribution} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                <XAxis dataKey="name" stroke="#52525b" fontSize={9} fontFamily="Courier New" tickLine={false} />
                <YAxis stroke="#52525b" fontSize={9} fontFamily="Courier New" tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" fill="#10b981" radius={[4, 4, 0, 0]}>
                  {patternDistribution.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={index % 2 === 0 ? "#10b981" : "#059669"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Line Chart - Trends of Alerts Over Time */}
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 h-80 flex flex-col">
        <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider mb-3">Fraud Trend History (7 Days)</span>
        <div className="flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData} margin={{ top: 10, right: 20, left: -10, bottom: 5 }}>
              <XAxis dataKey="date" stroke="#52525b" fontSize={9} fontFamily="Courier New" />
              <YAxis stroke="#52525b" fontSize={9} fontFamily="Courier New" />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 9, fontFamily: "Courier New", marginTop: 10 }} />
              <Line type="monotone" dataKey="alerts" name="Total Alerts" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="critical" name="Critical Cases" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Per-Bank Stats Table */}
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5">
        <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block mb-3">Detailed Bank & Tenant Metrics</span>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                <th className="py-2.5 px-3">Bank / Tenant</th>
                <th className="py-2.5 px-3">Country</th>
                <th className="py-2.5 px-3">Applicable Regulation</th>
                <th className="py-2.5 px-3">Risk Threshold</th>
                <th className="py-2.5 px-3 text-right">Registered Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-850 text-zinc-300">
              {tenants.map(t => (
                <tr key={t.id} className="hover:bg-zinc-950/40 transition">
                  <td className="py-3 px-3 font-bold text-zinc-200 flex items-center gap-2">
                    <Landmark className="w-3.5 h-3.5 text-zinc-500" />
                    {t.name}
                  </td>
                  <td className="py-3 px-3">
                    <span className="px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800 uppercase text-[10px]">
                      {t.country}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-zinc-400">{t.regulatoryFramework}</td>
                  <td className="py-3 px-3">
                    <span className="font-bold text-zinc-200">{(t.riskThreshold * 100)}%</span>
                  </td>
                  <td className="py-3 px-3 text-right">
                    <button
                      onClick={() => setSelectedTenantId(t.id)}
                      className="text-[10px] font-bold text-emerald-400 hover:text-emerald-300 border border-emerald-500/20 hover:border-emerald-500/40 rounded bg-emerald-500/5 px-2 py-1 transition cursor-pointer"
                    >
                      View Statistics
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
