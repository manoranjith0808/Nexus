import React, { useState, useEffect } from "react";
import { AgentReport, Alert } from "../types.js";
import { Shield, ShieldAlert, Cpu, Network, History, Scale, Wrench, Clock, CheckCircle2, AlertTriangle, ExternalLink, RefreshCw } from "lucide-react";

interface AgentReportsPanelProps {
  caseId: string;
  alert: Alert;
  activeRole: string; // "Analyst" | "Senior Analyst" | "Compliance Manager" | "Admin" | "Auditor"
  onTriggerResponse?: (action: string) => void;
}

export default function AgentReportsPanel({ caseId, alert, activeRole, onTriggerResponse }: AgentReportsPanelProps) {
  const [activeTab, setActiveTab] = useState<string>("1"); // Agent ID 1-6
  const [reports, setReports] = useState<Record<string, AgentReport>>({});
  const [isLoading, setIsLoading] = useState(false);

  // Load agent reports
  useEffect(() => {
    async function fetchReports() {
      setIsLoading(true);
      try {
        const fetched: Record<string, AgentReport> = {};
        for (let i = 1; i <= 6; i++) {
          const res = await fetch(`/api/cases/${caseId}/agents/${i}`);
          if (res.ok) {
            fetched[i.toString()] = await res.json();
          }
        }
        setReports(fetched);
      } catch (err) {
        console.error("Failed to load agent reports:", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchReports();
  }, [caseId]);

  const activeReport = reports[activeTab];

  const agentList = [
    { id: "1", name: "The Sentinel", icon: <Network className="w-4 h-4" />, desc: "Topology & Velocity" },
    { id: "2", name: "OSINT Agent", icon: <Cpu className="w-4 h-4" />, desc: "Digital Footprint & Redirects" },
    { id: "3", name: "Patterns Engine", icon: <Shield className="w-4 h-4" />, desc: "Models & MITRE ATT&CK" },
    { id: "4", name: "Historian Agent", icon: <History className="w-4 h-4" />, desc: "RAG & Threat Intel" },
    { id: "5", name: "The Jurist", icon: <Scale className="w-4 h-4" />, desc: "Verdict & Confidence" },
    { id: "6", name: "Executor Agent", icon: <Wrench className="w-4 h-4" />, desc: "Mitigation & SOC Response" }
  ];

  // Helper to render score gauges
  const renderScoreGauge = (score: number) => {
    const percentage = Math.round(score * 100);
    let color = "bg-emerald-500";
    if (score >= 0.8) color = "bg-rose-500";
    else if (score >= 0.5) color = "bg-amber-500";

    return (
      <div className="flex items-center gap-3">
        <div className="flex-1 bg-zinc-800 h-2 rounded-full overflow-hidden border border-zinc-700">
          <div className={`h-full ${color}`} style={{ width: `${percentage}%` }} />
        </div>
        <span className={`text-xs font-mono font-bold ${score >= 0.8 ? "text-rose-400" : score >= 0.5 ? "text-amber-400" : "text-emerald-400"}`}>
          {(score).toFixed(2)} ({percentage}%)
        </span>
      </div>
    );
  };

  const getSeverityBadge = (score: number) => {
    if (score >= 0.8) return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">CRITICAL</span>;
    if (score >= 0.5) return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">HIGH</span>;
    return <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">MEDIUM</span>;
  };

  return (
    <div className="flex flex-col lg:flex-row gap-5 h-full">
      {/* Agent Selector Sidebar */}
      <div className="lg:w-64 flex flex-row lg:flex-col gap-2 overflow-x-auto lg:overflow-x-visible pb-2 lg:pb-0">
        {agentList.map((ag) => {
          const isActive = activeTab === ag.id;
          const report = reports[ag.id];
          return (
            <button
              key={ag.id}
              onClick={() => setActiveTab(ag.id)}
              className={`flex-1 lg:flex-initial text-left p-3 rounded-lg border transition-all flex items-center gap-3 cursor-pointer ${
                isActive
                  ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-400 shadow-lg shadow-emerald-500/5"
                  : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <div className={`p-1.5 rounded-md ${isActive ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-800 text-zinc-500"}`}>
                {ag.icon}
              </div>
              <div className="min-w-0 hidden md:block">
                <div className="text-xs font-mono font-bold leading-tight flex items-center gap-1.5">
                  {ag.name}
                  {report?.isSimulated && (
                    <span className="text-[8px] px-1 py-0.2 rounded bg-zinc-800 text-zinc-500 border border-zinc-750">SIM</span>
                  )}
                </div>
                <div className="text-[10px] text-zinc-500 truncate leading-none mt-1">{ag.desc}</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Main Agent Details Panel */}
      <div className="flex-1 bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 flex flex-col relative overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 bg-zinc-950/70 backdrop-blur-xs flex items-center justify-center z-20">
            <div className="flex flex-col items-center gap-2">
              <RefreshCw className="w-6 h-6 text-emerald-400 animate-spin" />
              <span className="text-xs font-mono text-zinc-400">Analyzing swarm agents...</span>
            </div>
          </div>
        )}

        {activeReport ? (
          <div className="space-y-5 flex-1 flex flex-col justify-between">
            {/* Top Details Header */}
            <div>
              <div className="flex items-start justify-between border-b border-zinc-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <h3 className="text-sm font-mono font-bold text-zinc-200 uppercase tracking-wider">{activeReport.agentName}</h3>
                    {activeReport.isSimulated && (
                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 border border-zinc-700/50" title="Executed on reserve heuristic engines">
                        SIMULATED (RESERVE HEURISTICS)
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400">
                    Last Execution: <span className="font-mono text-zinc-300">{new Date(activeReport.timestamp).toLocaleTimeString()}</span>
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider mb-1">Threat Severity</div>
                  {getSeverityBadge(activeReport.riskScore)}
                </div>
              </div>

              {/* Grid with gauges */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-4">
                <div className="p-3.5 bg-zinc-950/40 rounded-lg border border-zinc-850">
                  <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase mb-2">Agent Risk Score</div>
                  {renderScoreGauge(activeReport.riskScore)}
                </div>
                <div className="p-3.5 bg-zinc-950/40 rounded-lg border border-zinc-850">
                  <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase mb-2">Confidence Interval</div>
                  {renderScoreGauge(activeReport.confidence)}
                </div>
              </div>

              {/* Unique agent special info rendering */}
              <div className="my-3">
                {activeTab === "1" && (
                  <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3.5 text-xs text-emerald-300">
                    <div className="font-mono font-bold text-[10px] uppercase text-emerald-400 mb-1.5 flex items-center gap-1.5">
                      <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                      REAL-TIME NETWORK MONITORING ACTIVE
                    </div>
                    <span>Continuous detection using advanced Neo4j GDS graph algorithms (Jaccard, Betweenness Centrality, PageRank) tracking illicit flows.</span>
                  </div>
                )}

                {activeTab === "2" && activeReport.evidence?.redirectTrace && (
                  <div className="bg-zinc-950/50 border border-zinc-800 rounded-lg p-3.5">
                    <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase mb-2">URL Redirection Chain (Link-Redirect Trace)</div>
                    <div className="space-y-1.5 font-mono text-[10px]">
                      {activeReport.evidence.redirectTrace.map((url: string, i: number) => {
                        const isFinal = i === activeReport.evidence.redirectTrace.length - 1;
                        return (
                          <div key={i} className="flex items-center gap-2">
                            <span className="text-zinc-500 font-bold">{i + 1}</span>
                            <span className={isFinal ? "text-rose-400 font-bold" : "text-zinc-300"}>{url}</span>
                            {isFinal && (
                              <span className="px-1 py-0.2 rounded bg-rose-500/10 text-rose-400 text-[8px] border border-rose-500/25 uppercase font-bold">
                                PHISHTANK BLACKLIST HIT
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {activeTab === "3" && activeReport.evidence?.mitreAttackTags && (
                  <div className="bg-zinc-950/50 border border-zinc-800 rounded-lg p-3.5">
                    <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase mb-2">Related MITRE ATT&CK Tactics</div>
                    <div className="flex flex-wrap gap-2">
                      {activeReport.evidence.mitreAttackTags.map((tag: string) => (
                        <a
                          key={tag}
                          href={`https://attack.mitre.org/techniques/${tag.split('.')[0]}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-emerald-400 hover:border-emerald-500/40 text-[10px] font-mono transition"
                        >
                          <span>{tag === "T1586" ? "T1586 (User Accounts)" : "T1586.002 (User Account Compromise)"}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === "4" && activeReport.evidence?.similarCases && (
                  <div className="bg-zinc-950/50 border border-zinc-800 rounded-lg p-3.5">
                    <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase mb-2">Similar Historic Cases Retrieved by RAG</div>
                    <div className="space-y-2">
                      {activeReport.evidence.similarCases.map((cs: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded bg-zinc-900/60 border border-zinc-850 text-xs font-mono">
                          <span className="text-zinc-300">{cs.caseId}</span>
                          <div className="flex items-center gap-3">
                            <span className="text-zinc-500">Similarity: {Math.round(cs.similarity * 100)}%</span>
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                              cs.outcome === "CONFIRMED_FRAUD" 
                                ? "bg-rose-500/10 text-rose-400 border border-rose-500/20" 
                                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            }`}>
                              {cs.outcome === "CONFIRMED_FRAUD" ? "TRUE POSITIVE (TP)" : "FALSE POSITIVE (FP)"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === "5" && (
                  <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3.5">
                    <div className="font-mono font-bold text-[10px] text-amber-400 uppercase mb-1.5 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4" />
                      SOVEREIGN JURIST RECOMMENDATION
                    </div>
                    <p className="text-xs text-zinc-300">
                      Suggested Verdict: <span className="font-bold text-zinc-100 uppercase">{activeReport.recommendation}</span>.
                    </p>
                    <p className="text-[10px] text-amber-500/90 font-bold mt-2 italic font-mono uppercase tracking-wider">
                      * THIS IS A RECOMMENDATION — THE FINAL DECISION ABSOLUTELY REQUIRES HUMAN ACTION (ANALYST).
                    </p>
                  </div>
                )}

                {activeTab === "6" && (
                  <div className="bg-zinc-950/50 border border-zinc-800 rounded-lg p-3.5">
                    <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase mb-2">Available SOC Contingency Actions (Limited Access)</div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                      {[
                        { id: "fw", name: "Add IP to Firewall blocklist (TBAL)", roleNeeded: "Senior Analyst" },
                        { id: "edr", name: "Trigger Endpoint AV/EDR Scan", roleNeeded: "Senior Analyst" },
                        { id: "isolate", name: "Isolate/Quarantine Digital Device", roleNeeded: "Senior Analyst" },
                        { id: "draft_ros", name: "Generate Regulatory SAR Draft", roleNeeded: "Analyst" }
                      ].map((act) => {
                        const hasRole = activeRole === "Admin" || activeRole === "Senior Analyst" || (activeRole === "Analyst" && act.roleNeeded === "Analyst");
                        return (
                          <button
                            key={act.id}
                            disabled={!hasRole}
                            onClick={() => onTriggerResponse && onTriggerResponse(act.name)}
                            className={`p-2.5 rounded text-left flex items-center justify-between text-xs font-mono transition border ${
                              hasRole
                                ? "bg-zinc-900 hover:bg-emerald-500/10 border-zinc-800 hover:border-emerald-500/30 text-zinc-300 cursor-pointer"
                                : "bg-zinc-950 border-zinc-900 text-zinc-600 cursor-not-allowed"
                            }`}
                          >
                            <span>{act.name}</span>
                            <span className={`text-[8px] px-1 rounded uppercase font-bold ${
                              hasRole ? "bg-zinc-850 text-zinc-400" : "bg-zinc-900 text-zinc-600"
                            }`}>
                              {act.roleNeeded}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                    <div className="mt-3 p-2 bg-zinc-900/40 rounded border border-zinc-850 flex items-center gap-2 text-[10px] font-mono text-zinc-400">
                      <ShieldAlert className="w-3.5 h-3.5 text-zinc-500" />
                      <span>Note: "Block Account" or "Cancel Transfer" requires direct manual action in the Core Banking system.</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Findings Checklist */}
              <div className="space-y-2 mt-4">
                <div className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider">Findings and Threat Signals</div>
                {activeReport.findings.length > 0 ? (
                  activeReport.findings.map((fd, i) => (
                    <div key={i} className="flex items-start gap-2.5 text-xs text-zinc-300 bg-zinc-950/20 p-2.5 rounded border border-zinc-850/40 font-mono">
                      <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                      <span>{fd}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-zinc-500 text-xs italic font-mono">No specific findings documented.</div>
                )}
              </div>
            </div>

            {/* Bottom Status bar */}
            <div className="border-t border-zinc-800 pt-3 flex items-center justify-between text-[10px] font-mono text-zinc-500 mt-4">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" /> Processing Latency: <span className="text-emerald-500 font-bold">{activeReport.latencyMs}ms</span>
              </span>
              <span>Nexus Sentinel Swarm (V2.4)</span>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-zinc-500 font-mono text-xs">
            No agent reports loaded for this case.
          </div>
        )}
      </div>
    </div>
  );
}
