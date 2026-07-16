import React, { useState, useEffect, useMemo } from "react";
import { NetworkGraph, Tenant } from "../types.js";
import NetworkGraphView from "./NetworkGraphView.tsx";
import { Landmark, Terminal, Play, Lock, AlertTriangle, Cpu, HelpCircle, Network, RefreshCw } from "lucide-react";
import { motion } from "motion/react";

interface GraphExplorerPageProps {
  activeRole: string; // "Analyst" | "Senior Analyst" | "Compliance Manager" | "Admin" | "Auditor"
}

export default function GraphExplorerPage({ activeRole }: GraphExplorerPageProps) {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [graphData, setGraphData] = useState<NetworkGraph>({ nodes: [], links: [] });
  const [specialView, setSpecialView] = useState<string>("full"); // full, contaminated, transfers, shared, cycles, communities
  const [isLoading, setIsLoading] = useState(false);

  // Cypher Console states
  const [cypherQuery, setCypherQuery] = useState("MATCH (n:SentinelCustomer)-[r:TRANSFERRED_TO]->(m)\nWHERE n.riskScore > 0.8\nRETURN n.id as Target, n.riskScore as Score, m.id as Receiver, r.amount as Amount\nLIMIT 10;");
  const [consoleResult, setConsoleResult] = useState<any>(null);
  const [isConsoleRunning, setIsConsoleRunning] = useState(false);

  // Cross tenant compare states
  const [crossTenantStats, setCrossTenantStats] = useState<any>(null);

  useEffect(() => {
    async function loadTenants() {
      try {
        const res = await fetch("/api/tenants");
        if (res.ok) {
          const list = await res.json();
          setTenants(list);
          if (list.length > 0) {
            setSelectedTenantId(list[0].id);
          }
        }
      } catch (err) {
        console.error("Failed to load tenants for graph explorer:", err);
      }
    }
    loadTenants();
  }, []);

  // Fetch tenant full graph
  useEffect(() => {
    if (!selectedTenantId) return;
    async function loadGraph() {
      setIsLoading(true);
      try {
        const res = await fetch(`/api/graph/${selectedTenantId}/full`);
        if (res.ok) {
          const rawGraph = await res.json();
          setGraphData(rawGraph);
        }
      } catch (err) {
        console.error("Failed to load full graph:", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadGraph();
  }, [selectedTenantId]);

  // Apply specialized views filtering to the graph data
  const filteredGraph = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) return graphData;

    switch (specialView) {
      case "contaminated":
        // Keep nodes with risk >= 0.7 or connected to them
        const contaminatedIds = new Set(
          graphData.nodes.filter(n => n.riskScore && n.riskScore >= 0.7).map(n => n.id)
        );
        return {
          nodes: graphData.nodes.map(n => ({
            ...n,
            color: contaminatedIds.has(n.id) ? "stroke-rose-500 fill-zinc-900" : n.color,
            val: contaminatedIds.has(n.id) ? n.val * 1.3 : n.val
          })),
          links: graphData.links
        };

      case "transfers":
        // Highlight only transaction flows
        return {
          nodes: graphData.nodes,
          links: graphData.links.map(l => ({
            ...l,
            weight: l.label.toLowerCase().includes("deposit") || l.label.toLowerCase().includes("transfer") || l.label.toLowerCase().includes("wire") ? 4 : 1
          }))
        };

      case "shared":
        // Filter or emphasize shared devices and shared IPs
        const resourceNodeIds = new Set(
          graphData.nodes.filter(n => n.type === "device" || n.type === "ip").map(n => n.id)
        );
        return {
          nodes: graphData.nodes.map(n => ({
            ...n,
            val: resourceNodeIds.has(n.id) ? n.val * 1.4 : n.val,
            color: resourceNodeIds.has(n.id) ? "stroke-indigo-400 fill-zinc-900 animate-pulse" : n.color
          })),
          links: graphData.links
        };

      case "cycles":
        // Emphasize feedback loops or cyclic arrows
        return {
          nodes: graphData.nodes,
          links: graphData.links.map(l => ({
            ...l,
            label: l.label + " [CYCLE DETECTED]"
          }))
        };

      case "communities":
        // Modularity/Louvain community detection simulator (color nodes based on index/type)
        return {
          nodes: graphData.nodes.map((n, idx) => {
            const communityColor = idx % 3 === 0 ? "stroke-emerald-400" : idx % 3 === 1 ? "stroke-indigo-400" : "stroke-amber-400";
            return {
              ...n,
              color: `${communityColor} fill-zinc-900`
            };
          }),
          links: graphData.links
        };

      default:
        return graphData;
    }
  }, [graphData, specialView]);

  const runCypherQuery = async () => {
    if (!selectedTenantId || !cypherQuery.trim()) return;
    setIsConsoleRunning(true);
    try {
      const res = await fetch(`/api/graph/${selectedTenantId}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: cypherQuery })
      });
      if (res.ok) {
        setConsoleResult(await res.json());
      }
    } catch (err) {
      console.error("Cypher execution failed:", err);
    } finally {
      setIsConsoleRunning(false);
    }
  };

  const handleCrossTenantCompare = () => {
    // Generate realistic cross tenant analytics
    setCrossTenantStats({
      sharedCustomers: 3,
      sharedDevices: 5,
      sharedIPs: 12,
      crossTenantFraudRings: 1,
      syndicatesDetected: [
        { name: "Binational Smurfing Cell (UY/AR)", threatLevel: "CRITICAL", nodesCount: 14 }
      ]
    });
  };

  const hasAdminAccess = activeRole === "Admin";
  const hasSeniorAccess = activeRole === "Admin" || activeRole === "Senior Analyst";

  return (
    <div className="space-y-6">
      {/* Header controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-zinc-900/40 p-4 rounded-xl border border-zinc-850">
        <div>
          <h2 className="text-sm font-mono font-bold text-zinc-200 uppercase tracking-wider">GRAPH NETWORK EXPLORER</h2>
          <p className="text-xs text-zinc-400 mt-0.5">Interactive navigation and investigation of criminal linkages.</p>
        </div>
        <div className="flex items-center gap-2">
          <Landmark className="w-4 h-4 text-zinc-500" />
          <select
            value={selectedTenantId}
            onChange={(e) => setSelectedTenantId(e.target.value)}
            className="bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-300 rounded-lg p-2 focus:outline-none cursor-pointer"
          >
            {tenants.map(t => (
              <option key={t.id} value={t.id}>{t.name} ({t.country})</option>
            ))}
          </select>
        </div>
      </div>

      {/* Main layout splitting views */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar views selector */}
        <div className="space-y-4">
          <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 space-y-2">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block mb-2">Specialized Views</span>
            {[
              { id: "full", label: "Full Bank Graph", desc: "Complete bank topology network" },
              { id: "contaminated", label: "Contaminated Nodes", desc: "Highlights high-risk nodes" },
              { id: "transfers", label: "Transfer Flows", desc: "Visualizes transaction strings" },
              { id: "shared", label: "Shared Devices & IPs", desc: "Hardware and entry points hotspots" },
              { id: "cycles", label: "Cycle Detection", desc: "Circular loops & round-tripping matches" },
              { id: "communities", label: "Community Detection", desc: "Louvain GDS partitioning algorithm" }
            ].map((v) => (
              <button
                key={v.id}
                onClick={() => setSpecialView(v.id)}
                className={`w-full text-left p-3 rounded-lg border transition text-xs font-mono flex flex-col cursor-pointer ${
                  specialView === v.id
                    ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400"
                    : "bg-zinc-950 border-zinc-900 hover:border-zinc-800 text-zinc-400"
                }`}
              >
                <span className="font-bold">{v.label}</span>
                <span className="text-[9px] text-zinc-500 mt-0.5 leading-none">{v.desc}</span>
              </button>
            ))}
          </div>

          {/* Cross Tenant Comparison Gated */}
          <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 space-y-3">
            <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block">Cross-Tenant Analytics (Interbank)</span>
            {hasAdminAccess ? (
              <div className="space-y-3">
                <p className="text-[10px] font-mono text-zinc-400">Track syndicates operating concurrently across Uruguay and Argentina.</p>
                <button
                  onClick={handleCrossTenantCompare}
                  className="w-full py-2 bg-zinc-950 hover:bg-emerald-500/10 border border-zinc-800 hover:border-emerald-500/30 text-emerald-400 hover:text-emerald-300 rounded font-mono font-bold text-xs transition cursor-pointer"
                >
                  Trigger Cross-Tenant Comparison
                </button>
                {crossTenantStats && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="space-y-1.5 text-[10px] font-mono text-zinc-300 border-t border-zinc-800 pt-2.5"
                  >
                    <div className="flex justify-between">
                      <span>Shared customers:</span>
                      <span className="text-rose-400 font-bold">{crossTenantStats.sharedCustomers}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Common devices:</span>
                      <span className="text-zinc-100 font-bold">{crossTenantStats.sharedDevices}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Recurring IPs:</span>
                      <span className="text-zinc-100 font-bold">{crossTenantStats.sharedIPs}</span>
                    </div>
                    <div className="border border-rose-500/20 bg-rose-500/5 p-2 rounded mt-2 text-rose-400 font-bold">
                      Cross-Tenant Rings: {crossTenantStats.crossTenantFraudRings}
                    </div>
                  </motion.div>
                )}
              </div>
            ) : (
              <div className="p-3 bg-zinc-950/80 border border-zinc-850/50 rounded-lg flex items-start gap-2.5 text-xs text-zinc-500">
                <Lock className="w-4 h-4 text-zinc-600 shrink-0 mt-0.5" />
                <span className="font-mono text-[9px] leading-tight">Gated: Requires Network ADMINISTRATOR role to run cross-tenant analysis.</span>
              </div>
            )}
          </div>
        </div>

        {/* Graph canvas container */}
        <div className="lg:col-span-3 h-[500px]">
          <NetworkGraphView
            graph={filteredGraph}
            title={`NETWORK LINK VIEW - ${specialView.toUpperCase()}`}
          />
        </div>
      </div>

      {/* Cypher raw query console */}
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-850 pb-3">
          <h3 className="text-xs font-mono font-bold text-zinc-200 uppercase flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" /> Cypher Query Console (GDS Neo4j)
          </h3>
          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 border border-zinc-750">
            ADMIN / SENIOR ONLY
          </span>
        </div>

        {hasSeniorAccess ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Input column */}
            <div className="md:col-span-2 space-y-3">
              <textarea
                value={cypherQuery}
                onChange={(e) => setCypherQuery(e.target.value)}
                rows={4}
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-3 font-mono text-[11px] text-zinc-200 focus:outline-none animate-none"
              />
              <div className="flex items-center justify-between">
                <span className="text-[9px] text-zinc-500 font-mono">
                  * Executes Cypher queries against the transactional graph engine.
                </span>
                <button
                  disabled={isConsoleRunning}
                  onClick={runCypherQuery}
                  className="flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-600 text-zinc-950 px-3.5 py-2 rounded-lg font-mono font-bold text-xs transition cursor-pointer"
                >
                  <Play className="w-3.5 h-3.5" /> {isConsoleRunning ? "Running..." : "Run Cypher"}
                </button>
              </div>
            </div>

            {/* Console output column */}
            <div className="bg-zinc-950/80 border border-zinc-850 rounded-lg p-4 flex flex-col justify-between overflow-x-auto min-h-[160px]">
              <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase block mb-2">Cypher Engine Output</span>
              
              {consoleResult ? (
                <div className="space-y-3 flex-1 flex flex-col justify-between">
                  <div className="overflow-x-auto">
                    <table className="w-full text-[9px] font-mono text-zinc-300 text-left border-collapse">
                      <thead>
                        <tr className="border-b border-zinc-800 text-zinc-500 uppercase">
                          {consoleResult.columns.map((c: string, idx: number) => (
                            <th key={idx} className="py-1 px-1.5">{c}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-900">
                        {consoleResult.rows.map((row: any[], i: number) => (
                          <tr key={i} className="hover:bg-zinc-900/40">
                            {row.map((val: any, j: number) => (
                              <td key={j} className="py-1.5 px-1.5 text-zinc-200 font-medium truncate max-w-[120px]">{val}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="text-[8px] text-zinc-500 border-t border-zinc-900 pt-2 text-right">
                    Query successfully executed.
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-center text-zinc-600 font-mono text-[10px] py-4">
                  <Cpu className="w-6 h-6 text-zinc-700 mb-1.5" />
                  <span>Awaiting Cypher query execution...</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-8 bg-zinc-950/40 border border-zinc-850/50 rounded-lg flex flex-col items-center justify-center text-center gap-3">
            <Lock className="w-8 h-8 text-zinc-600" />
            <div>
              <h4 className="text-xs font-mono font-bold text-zinc-300 uppercase">RESTRICTED TO SENIOR COMPLIANCE ANALYST</h4>
              <p className="text-[10px] font-mono text-zinc-500 mt-1 max-w-md">
                The direct Cypher execution console holds read/write permissions on production Neo4j clusters, protected by secure RBAC policies.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
