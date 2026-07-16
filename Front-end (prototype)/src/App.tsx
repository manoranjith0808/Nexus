import React, { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { 
  Shield, 
  ShieldAlert, 
  Users, 
  Database, 
  Activity, 
  Network, 
  Settings, 
  Clock, 
  Search, 
  Filter, 
  UserPlus, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Lock, 
  ChevronRight, 
  Download, 
  Printer, 
  LogOut, 
  Terminal, 
  PlusCircle, 
  TrendingUp, 
  RefreshCw,
  FileText 
} from "lucide-react";

import { Alert, CaseStatus, Verdict, PatternType } from "./types.js";
import AgentReportsPanel from "./components/AgentReportsPanel.tsx";
import NetworkGraphView from "./components/NetworkGraphView.tsx";
import ManagerDashboard from "./components/ManagerDashboard.tsx";
import TenantManagement from "./components/TenantManagement.tsx";
import GraphExplorerPage from "./components/GraphExplorerPage.tsx";
import EventSubmissionTesting from "./components/EventSubmissionTesting.tsx";

const queryClient = new QueryClient();

// Available Roles for testing RBAC
const ROLES = [
  { id: "Analyst", name: "Compliance Analyst (L1)", desc: "Gestiona colas y toma decisiones" },
  { id: "Senior Analyst", name: "Senior Analyst (L2)", desc: "Analista Senior + Ejecución de Respuesta SOC" },
  { id: "Compliance Manager", name: "Compliance Manager", desc: "Ver estadísticas globales sin decidir" },
  { id: "Admin", name: "Platform Admin", desc: "CRUD total + Consola Cypher + Cross-Tenant" },
  { id: "Auditor", name: "Regulatory Auditor", desc: "Acceso de lectura y auditoría" }
];

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NexusApp />
    </QueryClientProvider>
  );
}

function NexusApp() {
  // Navigation
  const [currentView, setCurrentView] = useState<"queue" | "case" | "dashboard" | "tenants" | "graph-explorer" | "testing">("queue");
  
  // Role & Authentication Context (Simulated)
  const [activeRole, setActiveRole] = useState<string>("Analyst");
  const [userEmail, setUserEmail] = useState("analyst@nexus.com");

  // Alert Queue States
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [queueStats, setQueueStats] = useState<any>({ pending: 0, critical: 0, total: 0, resolved: 0 });
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [isLoadingQueue, setIsLoadingQueue] = useState(false);

  // Queue Filters
  const [filterVerdict, setFilterVerdict] = useState<string>("all");
  const [filterCountry, setFilterCountry] = useState<string>("all");
  const [filterTenant, setFilterTenant] = useState<string>("all");
  const [minScore, setMinScore] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState("");

  // Case Investigation States
  const [caseDetails, setCaseDetails] = useState<any>(null);
  const [activeCaseTab, setActiveCaseTab] = useState<"narrative" | "agents" | "graph" | "ros" | "history">("narrative");
  const [isLoadingCase, setIsLoadingCase] = useState(false);

  // Decision Panel fields
  const [decisionVerdict, setDecisionVerdict] = useState<Verdict>(Verdict.BLOCK);
  const [decisionComments, setDecisionComments] = useState("");

  // Global Tenant Store (for dropdown filters)
  const [tenants, setTenants] = useState<any[]>([]);

  // Trigger feedback messages
  const [systemNotification, setSystemNotification] = useState<{ type: "success" | "warn"; msg: string } | null>(null);

  // 1. Fetch Alert Queue & Stats with Polling
  const fetchQueue = async () => {
    setIsLoadingQueue(true);
    try {
      // Assemble queries
      const params = new URLSearchParams();
      if (filterVerdict !== "all") params.append("verdict", filterVerdict);
      if (filterCountry !== "all") params.append("country", filterCountry);
      if (filterTenant !== "all") params.append("tenantId", filterTenant);
      if (minScore > 0) params.append("minScore", minScore.toString());

      const resQueue = await fetch(`/api/alerts/queue?${params.toString()}`);
      if (resQueue.ok) {
        let list = await resQueue.json();
        // Client-side search match
        if (searchQuery.trim()) {
          list = list.filter((a: Alert) => 
            a.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            a.customerDocument.toLowerCase().includes(searchQuery.toLowerCase()) ||
            a.id.toLowerCase().includes(searchQuery.toLowerCase())
          );
        }
        setAlerts(list);
      }

      const resStats = await fetch("/api/alerts/queue/stats");
      if (resStats.ok) {
        setQueueStats(await resStats.json());
      }
    } catch (err) {
      console.error("Failed to load alerts queue:", err);
    } finally {
      setIsLoadingQueue(false);
    }
  };

  useEffect(() => {
    fetchQueue();
    // Fetch tenants too
    const loadTenants = async () => {
      const res = await fetch("/api/tenants");
      if (res.ok) setTenants(await res.json());
    };
    loadTenants();

    // Polling interval: Refresh queue every 12 seconds
    const interval = setInterval(() => {
      fetchQueue();
    }, 12000);

    return () => clearInterval(interval);
  }, [filterVerdict, filterCountry, filterTenant, minScore, searchQuery]);

  // Update user info automatically based on role selected
  useEffect(() => {
    if (activeRole === "Analyst") setUserEmail("analyst@nexus.com");
    else if (activeRole === "Senior Analyst") setUserEmail("senior_analyst@nexus.com");
    else if (activeRole === "Compliance Manager") setUserEmail("manager@nexus.com");
    else if (activeRole === "Admin") setUserEmail("admin@nexus.com");
    else if (activeRole === "Auditor") setUserEmail("auditor@nexus.com");
  }, [activeRole]);

  // 2. Load Single Case Detail
  const handleOpenCase = async (caseId: string) => {
    setIsLoadingCase(true);
    setSelectedCaseId(caseId);
    setCurrentView("case");
    setActiveCaseTab("narrative");
    try {
      const res = await fetch(`/api/cases/${caseId}`);
      if (res.ok) {
        setCaseDetails(await res.json());
      }
    } catch (err) {
      console.error("Failed to load case details:", err);
    } finally {
      setIsLoadingCase(false);
    }
  };

  // 3. Assign Analyst Action
  const handleAssignCase = async (caseId: string) => {
    try {
      const res = await fetch(`/api/alerts/${caseId}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analystName: userEmail })
      });
      if (res.ok) {
        triggerNotification("success", "Caso auto-asignado con éxito");
        fetchQueue();
        if (selectedCaseId === caseId) {
          // reload current case
          const resCase = await fetch(`/api/cases/${caseId}`);
          if (resCase.ok) setCaseDetails(await resCase.json());
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 4. Decide Case Action
  const handleDecideCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId) return;

    try {
      const res = await fetch(`/api/alerts/${selectedCaseId}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          verdict: decisionVerdict,
          comments: decisionComments,
          analystName: userEmail,
          analystRole: activeRole
        })
      });

      if (res.ok) {
        triggerNotification("success", `Dictamen guardado como: ${decisionVerdict}`);
        setDecisionComments("");
        handleOpenCase(selectedCaseId); // refresh case
        fetchQueue();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 5. Trigger SOC action response feedback
  const handleTriggerResponseAction = (actionName: string) => {
    triggerNotification("success", `Iniciando acción de respuesta SOC: ${actionName}`);
    // Record into logs
    if (caseDetails) {
      const updatedLogs = [
        {
          id: "audit-" + Date.now(),
          caseId: selectedCaseId!,
          timestamp: new Date().toISOString(),
          user: userEmail,
          role: activeRole,
          action: "Respuesta de Emergencia SOC",
          details: `Se disparó la mitigación técnica: "${actionName}".`
        },
        ...caseDetails.auditLogs
      ];
      setCaseDetails({
        ...caseDetails,
        auditLogs: updatedLogs
      });
    }
  };

  const triggerNotification = (type: "success" | "warn", msg: string) => {
    setSystemNotification({ type, msg });
    setTimeout(() => setSystemNotification(null), 4000);
  };

  // Print ROS Sheet
  const handlePrintROS = () => {
    window.print();
  };

  // Score Bar Render Widget
  const renderScoreBar = (score: number) => {
    const percentage = Math.round(score * 100);
    let barColor = "bg-emerald-500";
    let textColor = "text-emerald-400";

    if (score >= 0.8) {
      barColor = "bg-rose-500 shadow-sm shadow-rose-500/30 animate-pulse";
      textColor = "text-rose-400 font-bold";
    } else if (score >= 0.5) {
      barColor = "bg-amber-500";
      textColor = "text-amber-400";
    }

    return (
      <div className="flex items-center gap-2 font-mono">
        <span className={`text-[11px] w-8 ${textColor}`}>{(score).toFixed(2)}</span>
        <div className="w-16 bg-zinc-800 h-1.5 rounded-full overflow-hidden border border-zinc-700/50">
          <div className={`h-full ${barColor}`} style={{ width: `${percentage}%` }} />
        </div>
      </div>
    );
  };

  const getVerdictStyle = (v: Verdict) => {
    switch (v) {
      case Verdict.BLOCK:
        return "bg-rose-500/10 text-rose-400 border border-rose-500/20";
      case Verdict.ESCALATE:
        return "bg-orange-500/10 text-orange-400 border border-orange-500/20";
      case Verdict.MONITOR:
        return "bg-amber-500/10 text-amber-400 border border-amber-500/20";
      default:
        return "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
    }
  };

  return (
    <div className="min-h-screen bg-[#07070a] text-zinc-100 flex font-sans overflow-x-hidden selection:bg-emerald-500 selection:text-zinc-900">
      
      {/* Top Floating Notification banner */}
      {systemNotification && (
        <div className="fixed top-4 right-4 z-50 animate-bounce">
          <div className={`flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-2xl backdrop-blur-md ${
            systemNotification.type === "success" 
              ? "bg-zinc-900/90 border-emerald-500/50 text-emerald-400" 
              : "bg-zinc-900/90 border-amber-500/50 text-amber-400"
          }`}>
            <CheckCircle className="w-4 h-4 shrink-0" />
            <span className="font-mono text-xs font-bold uppercase">{systemNotification.msg}</span>
          </div>
        </div>
      )}

      {/* SIDEBAR NAVIGATION - Persitent */}
      <aside className="w-64 border-r border-zinc-850 bg-[#0a0a0e] flex flex-col justify-between shrink-0 hidden md:flex">
        <div className="flex flex-col flex-1">
          {/* Main Title branding */}
          <div className="p-5 border-b border-zinc-850">
            <div className="flex items-center gap-2">
              <Shield className="w-6 h-6 text-emerald-400 animate-pulse" />
              <div>
                <h1 className="text-sm font-mono font-extrabold tracking-wider text-zinc-100 leading-none">NEXUS</h1>
                <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase tracking-widest mt-0.5 block">Sentinel Swarm v2</span>
              </div>
            </div>
          </div>

          {/* Current Role switcher widget - Top of Sidebar */}
          <div className="p-4 bg-zinc-950/60 border-b border-zinc-900">
            <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase tracking-wider block mb-2">Simular Rol Analista (RBAC)</span>
            <select
              value={activeRole}
              onChange={(e) => setActiveRole(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 text-[10px] font-mono text-zinc-300 rounded p-1.5 focus:outline-none focus:border-emerald-500/40"
            >
              {ROLES.map(r => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <span className="text-[8px] font-mono text-zinc-500 mt-1 block truncate">
              ID: {userEmail}
            </span>
          </div>

          {/* Main Navigation links */}
          <nav className="p-3.5 space-y-1">
            <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase tracking-widest block px-3 mb-2">Centro de Control</span>
            
            <button
              onClick={() => { setCurrentView("queue"); setSelectedCaseId(null); }}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-mono transition ${
                currentView === "queue" 
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30 border border-transparent"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Database className="w-4 h-4" />
                <span>Cola de Alertas</span>
              </div>
              <span className="text-[10px] font-bold font-mono px-1.5 py-0.2 rounded bg-zinc-900 border border-zinc-800 text-zinc-500">
                {alerts.length}
              </span>
            </button>

            {selectedCaseId && (
              <button
                onClick={() => setCurrentView("case")}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-mono transition ${
                  currentView === "case" 
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30 border border-transparent"
                }`}
              >
                <ShieldAlert className="w-4 h-4 text-rose-400 animate-pulse" />
                <span className="truncate">Caso {selectedCaseId}</span>
              </button>
            )}

            <button
              onClick={() => setCurrentView("dashboard")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-mono transition ${
                currentView === "dashboard" 
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30 border border-transparent"
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Manager Dashboard</span>
            </button>

            <button
              onClick={() => setCurrentView("graph-explorer")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-mono transition ${
                currentView === "graph-explorer" 
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30 border border-transparent"
              }`}
            >
              <Network className="w-4 h-4" />
              <span>Explorador de Grafos</span>
            </button>

            <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase tracking-widest block px-3 pt-4 mb-2">Administración</span>

            <button
              onClick={() => setCurrentView("tenants")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-mono transition ${
                currentView === "tenants" 
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30 border border-transparent"
              }`}
            >
              <Users className="w-4 h-4" />
              <span>Gestión de Bancos</span>
            </button>

            <button
              onClick={() => setCurrentView("testing")}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-xs font-mono transition ${
                currentView === "testing" 
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30 border border-transparent"
              }`}
            >
              <PlusCircle className="w-4 h-4" />
              <span>Simulación de Eventos</span>
            </button>
          </nav>
        </div>

        {/* Auditor regulatory compliance footnote */}
        <div className="p-4 border-t border-zinc-850/80 text-[10px] text-zinc-500 space-y-1 bg-zinc-950/40">
          <p className="font-mono uppercase font-bold text-[9px] text-zinc-400">LATAM COMPLIANCE</p>
          <p>BCU Circular 315/2022</p>
          <p>UIF Res 14/2023</p>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col overflow-y-auto">
        
        {/* Header Ribbon bar */}
        <header className="h-16 border-b border-zinc-850/80 bg-[#0a0a0e] px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <span className="text-xs font-mono font-bold text-zinc-400 hidden sm:inline-block">
              PLATAFORMA DE DECISIONES DE FRAUDE
            </span>
            <div className="h-4 w-px bg-zinc-800 hidden sm:block" />
            <span className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-1.5">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              SISTEMA ONLINE
            </span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-zinc-950/60 border border-zinc-850 px-3 py-1.5 rounded-lg text-xs font-mono text-zinc-300">
              <span className="text-zinc-500">ROL ACTIVO:</span>
              <span className="font-bold text-emerald-400 uppercase tracking-wider">{activeRole}</span>
            </div>
          </div>
        </header>

        {/* Content Stages */}
        <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
          
          {/* 1. ALERT QUEUE STAGE */}
          {currentView === "queue" && (
            <div className="space-y-6">
              
              {/* Summary Stats Strip */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { label: "Bandeja de Entrada", value: queueStats.pending, color: "text-zinc-100", border: "border-zinc-800" },
                  { label: "Alertas Críticas", value: queueStats.critical, color: "text-rose-400", border: "border-rose-500/25" },
                  { label: "Casos Consolidados", value: queueStats.total, color: "text-zinc-400", border: "border-zinc-850" },
                  { label: "Resueltos / Cerrados", value: queueStats.resolved, color: "text-emerald-400", border: "border-emerald-500/25" }
                ].map((st, idx) => (
                  <div key={idx} className={`bg-zinc-900/30 border rounded-xl p-4 flex flex-col justify-between ${st.border}`}>
                    <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider">{st.label}</span>
                    <span className={`text-2xl font-mono font-extrabold mt-1 ${st.color}`}>{st.value}</span>
                  </div>
                ))}
              </div>

              {/* Filters Block */}
              <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4.5 space-y-3">
                <div className="flex items-center gap-2 border-b border-zinc-850 pb-2">
                  <Filter className="w-4 h-4 text-zinc-400" />
                  <span className="text-xs font-mono font-bold text-zinc-300 uppercase">Filtros Avanzados de Cola</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  {/* Verdict Select */}
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono font-bold text-zinc-500 uppercase">Dictamen</label>
                    <select
                      value={filterVerdict}
                      onChange={(e) => setFilterVerdict(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 font-mono text-xs text-zinc-300 focus:outline-none"
                    >
                      <option value="all">TODOS</option>
                      <option value="BLOCK">BLOCK</option>
                      <option value="ESCALATE">ESCALATE</option>
                      <option value="MONITOR">MONITOR</option>
                      <option value="DISCARD">DISCARD</option>
                    </select>
                  </div>

                  {/* Country select */}
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono font-bold text-zinc-500 uppercase">Jurisdicción</label>
                    <select
                      value={filterCountry}
                      onChange={(e) => setFilterCountry(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 font-mono text-xs text-zinc-300 focus:outline-none"
                    >
                      <option value="all">TODAS (UY / AR)</option>
                      <option value="UY">URUGUAY (UY)</option>
                      <option value="AR">ARGENTINA (AR)</option>
                    </select>
                  </div>

                  {/* Tenant select */}
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono font-bold text-zinc-500 uppercase">Banco Inquilino</label>
                    <select
                      value={filterTenant}
                      onChange={(e) => setFilterTenant(e.target.value)}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2 font-mono text-xs text-zinc-300 focus:outline-none"
                    >
                      <option value="all">TODOS LOS BANCOS</option>
                      {tenants.map(t => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Min Score slide */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[9px] font-mono font-bold text-zinc-500">
                      <span>Riesgo Mínimo</span>
                      <span className="text-emerald-400">{Math.round(minScore * 100)}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="0.95"
                      step="0.05"
                      value={minScore}
                      onChange={(e) => setMinScore(parseFloat(e.target.value))}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-emerald-400 mt-2.5"
                    />
                  </div>

                  {/* Text search */}
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono font-bold text-zinc-500 uppercase">Buscador Cliente / Doc</label>
                    <div className="relative">
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="ej. Eduardo, C.I., CUIT..."
                        className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg pl-8 pr-3 py-2 font-mono text-xs text-zinc-200 focus:outline-none"
                      />
                      <Search className="w-3.5 h-3.5 text-zinc-600 absolute left-2.5 top-2.5" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Queue Table */}
              <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl overflow-hidden">
                <div className="px-5 py-3.5 border-b border-zinc-850 flex items-center justify-between bg-zinc-900/40">
                  <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-wider">BANDEJA DE TRABAJO ACTIVAS ({alerts.length})</span>
                  <button
                    onClick={fetchQueue}
                    className="p-1.5 rounded bg-zinc-950 hover:bg-zinc-900 border border-zinc-850 hover:border-zinc-750 text-zinc-400 hover:text-zinc-200 text-[10px] font-mono font-bold transition flex items-center gap-1 cursor-pointer"
                  >
                    <RefreshCw className="w-3 h-3" /> Sincronizar Cola
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs font-mono">
                    <thead>
                      <tr className="border-b border-zinc-850 text-zinc-500 text-[10px] uppercase bg-zinc-950/20">
                        <th className="py-3 px-4">Caso ID</th>
                        <th className="py-3 px-4">Banco Inquilino</th>
                        <th className="py-3 px-4">Cliente / Documento</th>
                        <th className="py-3 px-4">Patrón</th>
                        <th className="py-3 px-4">Riesgo / Confianza</th>
                        <th className="py-3 px-4">Monto Evaluado</th>
                        <th className="py-3 px-4">Recomendación</th>
                        <th className="py-3 px-4 text-right">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-850 text-zinc-300">
                      {alerts.length > 0 ? (
                        alerts.map((al) => (
                          <tr
                            key={al.id}
                            className="hover:bg-zinc-950/60 transition cursor-pointer group"
                            onClick={() => handleOpenCase(al.id)}
                          >
                            <td className="py-4 px-4 font-bold text-zinc-200 font-mono text-emerald-400 group-hover:underline">
                              {al.id}
                            </td>
                            <td className="py-4 px-4">
                              <div className="font-bold text-zinc-200">{al.tenantName}</div>
                              <div className="text-[10px] text-zinc-500 uppercase">{al.country}</div>
                            </td>
                            <td className="py-4 px-4">
                              <div className="font-bold text-zinc-100">{al.customerName}</div>
                              <div className="text-[10px] text-zinc-400">{al.customerDocument}</div>
                            </td>
                            <td className="py-4 px-4">
                              <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-850 text-zinc-300 text-[9px] font-bold">
                                {al.pattern}
                              </span>
                            </td>
                            <td className="py-4 px-4 space-y-1.5">
                              {renderScoreBar(al.riskScore)}
                              <div className="text-[9px] text-zinc-500">Conf: {Math.round(al.confidenceScore * 100)}%</div>
                            </td>
                            <td className="py-4 px-4">
                              <div className="font-bold text-zinc-200">
                                {al.currency} {(al.amount).toLocaleString()}
                              </div>
                            </td>
                            <td className="py-4 px-4">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${getVerdictStyle(al.verdict)}`}>
                                {al.verdict}
                              </span>
                            </td>
                            <td className="py-4 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                              {al.assignedTo ? (
                                <span className="text-[10px] text-zinc-500 font-mono italic">
                                  Asignado a: {al.assignedTo === userEmail ? "Ti" : al.assignedTo.split('@')[0]}
                                </span>
                              ) : (
                                <button
                                  onClick={() => handleAssignCase(al.id)}
                                  className="text-[10px] font-bold text-emerald-400 hover:text-emerald-300 border border-emerald-500/20 hover:border-emerald-500/40 rounded bg-emerald-500/5 px-2.5 py-1.5 transition cursor-pointer"
                                >
                                  Tomar Caso
                                </button>
                              )}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={8} className="py-8 text-center text-zinc-500 font-mono text-xs">
                            Ninguna alerta activa que coincida con los filtros aplicados.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          )}

          {/* 2. CASE VIEW / INVESTIGATION STAGE */}
          {currentView === "case" && selectedCaseId && caseDetails && (
            <div className="space-y-6">
              
              {/* Case Header Details bar */}
              <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div className="flex items-start gap-3">
                  <div className="p-3 bg-zinc-950 rounded-xl border border-zinc-850 text-rose-400">
                    <ShieldAlert className="w-6 h-6 animate-pulse" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-sm font-mono font-bold text-zinc-100 uppercase">EXPEDIENTE DIGITAL DE INVESTIGACIÓN · {selectedCaseId}</h2>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/15 text-rose-400 border border-rose-500/20 uppercase">
                        {caseDetails.alert.status}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      Cliente: <span className="font-bold text-zinc-200 font-mono">{caseDetails.alert.customerName}</span> | 
                      Documento: <span className="font-mono text-zinc-200">{caseDetails.alert.customerDocument}</span> |
                      Banco: <span className="font-bold text-emerald-400 uppercase font-mono">{caseDetails.alert.tenantName} ({caseDetails.alert.country})</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => { setCurrentView("queue"); setSelectedCaseId(null); }}
                    className="px-3.5 py-2 rounded-lg border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/30 font-mono text-xs transition cursor-pointer"
                  >
                    Volver a la Cola
                  </button>
                </div>
              </div>

              {/* Tabbed Layout buttons */}
              <div className="flex border-b border-zinc-850 text-xs font-mono overflow-x-auto pb-0.5">
                {[
                  { id: "narrative", label: "NARRATIVA & EXPLICACIÓN AI" },
                  { id: "agents", label: "AGENTES SWARM (6)" },
                  { id: "graph", label: "SUBGRAFO DE VINCULACIÓN" },
                  { id: "ros", label: "REPORTE DE SOSPECHA (ROS)" },
                  { id: "history", label: "AUDIT LOG & TIMELINE" }
                ].map((tb) => (
                  <button
                    key={tb.id}
                    onClick={() => setActiveCaseTab(tb.id as any)}
                    className={`pb-2.5 px-4 font-bold border-b-2 transition uppercase whitespace-nowrap ${
                      activeCaseTab === tb.id ? "border-emerald-500 text-emerald-400" : "border-transparent text-zinc-500 hover:text-zinc-300"
                    }`}
                  >
                    {tb.label}
                  </button>
                ))}
              </div>

              {/* Tab contents */}
              <div className="min-h-[380px]">
                
                {/* TAB 1: Narrative & AI reasoning */}
                {activeCaseTab === "narrative" && (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Narrative panel */}
                    <div className="lg:col-span-2 space-y-4">
                      <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-3.5">
                        <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-850 pb-2">Narrativa de Operación Sospechosa</span>
                        <p className="text-xs text-zinc-300 leading-relaxed font-mono">
                          {caseDetails.narrative}
                        </p>
                      </div>

                      <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-3.5">
                        <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-850 pb-2">Dictamen Automatizado del Jurista Soberano (Agente 5)</span>
                        
                        <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-4 text-xs font-mono text-zinc-300">
                          <div className="flex items-center gap-2 text-amber-400 font-bold mb-1.5 uppercase tracking-wider text-[11px]">
                            <AlertTriangle className="w-4 h-4" />
                            RECOMENDACIÓN DE SISTEMA: {caseDetails.alert.verdict} (CONFIDENCIA: {Math.round(caseDetails.alert.confidenceScore * 100)}%)
                          </div>
                          <p className="italic">
                            "El Jurista determinó recomendación {caseDetails.alert.verdict} basada en la estructuración de giros y la inconsistencia absoluta del perfil del cliente con el volumen observado."
                          </p>
                          <div className="mt-3 text-[10px] text-amber-500/90 font-bold border-t border-amber-500/10 pt-2 uppercase">
                            * ADVERTENCIA: ESTO ES UNA RECOMENDACIÓN AUTOMATIZADA — SE REQUIERE ABSOLUTAMENTE UNA DECISIÓN FINAL POR UN ANALISTA HUMANO.
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* AI Reasoning numbered step by step */}
                    <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-4">
                      <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-850 pb-2">Razonamiento AI de Enjambre (Step-by-Step)</span>
                      
                      <div className="space-y-4 font-mono">
                        {caseDetails.aiReasoning.map((step: string, i: number) => (
                          <div key={i} className="flex gap-3 text-xs text-zinc-300">
                            <span className="w-5 h-5 rounded bg-zinc-900 border border-zinc-800 text-emerald-400 flex items-center justify-center font-bold shrink-0">
                              {i + 1}
                            </span>
                            <span className="leading-relaxed">{step}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 2: Agent scores */}
                {activeCaseTab === "agents" && (
                  <AgentReportsPanel
                    caseId={selectedCaseId}
                    alert={caseDetails.alert}
                    activeRole={activeRole}
                    onTriggerResponse={handleTriggerResponseAction}
                  />
                )}

                {/* TAB 3: Graph */}
                {activeCaseTab === "graph" && (
                  <div className="h-[460px]">
                    <NetworkGraphView
                      graph={caseDetails.graph}
                      title={`SUBGRAFO DE COMPORTAMIENTO CASO ${selectedCaseId}`}
                    />
                  </div>
                )}

                {/* TAB 4: ROS Report (printable) */}
                {activeCaseTab === "ros" && (
                  <div className="space-y-4">
                    {/* Header bar print */}
                    <div className="flex items-center justify-between bg-zinc-900/40 p-4 rounded-xl border border-zinc-850 print:hidden">
                      <div>
                        <h4 className="text-xs font-mono font-bold text-zinc-200">BORRADOR COMPLETO REPORTE ROS NORMADO</h4>
                        <p className="text-[10px] text-zinc-500 font-mono">Generado automáticamente bajo normativas ALA/CFT.</p>
                      </div>
                      <button
                        onClick={handlePrintROS}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-zinc-950 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-300 font-mono text-xs transition cursor-pointer"
                      >
                        <Printer className="w-4 h-4" /> Imprimir / PDF
                      </button>
                    </div>

                    {/* Report Form Sheet */}
                    <div className="bg-white text-zinc-900 p-8 rounded-xl shadow-2xl border border-zinc-300 font-serif max-w-4xl mx-auto print:p-0 print:border-none print:shadow-none">
                      <div className="text-center space-y-2 border-b-2 border-zinc-800 pb-4">
                        <h1 className="text-lg font-bold font-sans uppercase tracking-wider text-zinc-800">Reporte de Operación Sospechosa (ROS)</h1>
                        <p className="text-xs font-mono uppercase text-zinc-500">Unidad de Información y Análisis Financiero / Banco Central</p>
                      </div>

                      <div className="grid grid-cols-2 gap-4 my-6 text-xs font-mono">
                        <div>
                          <p className="font-bold text-zinc-600">Sujeto Reportado:</p>
                          <p className="text-sm font-bold text-zinc-800">{caseDetails.rosReport.subjectName}</p>
                        </div>
                        <div>
                          <p className="font-bold text-zinc-600">Documento:</p>
                          <p className="text-sm font-bold text-zinc-800">{caseDetails.rosReport.documentType} {caseDetails.rosReport.documentNumber}</p>
                        </div>
                        <div>
                          <p className="font-bold text-zinc-600">Fecha de Reporte:</p>
                          <p className="text-zinc-800">{caseDetails.rosReport.reportDate}</p>
                        </div>
                        <div>
                          <p className="font-bold text-zinc-600">Inquilino / Banco Remitente:</p>
                          <p className="text-zinc-800">{caseDetails.alert.tenantName}</p>
                        </div>
                        <div>
                          <p className="font-bold text-zinc-600">Código Normativa Aplicada:</p>
                          <p className="text-zinc-800">{caseDetails.rosReport.regulatoryCode}</p>
                        </div>
                        <div>
                          <p className="font-bold text-zinc-600">Patrón de Sospecha:</p>
                          <p className="text-zinc-800 uppercase font-bold text-rose-600">{caseDetails.alert.pattern}</p>
                        </div>
                      </div>

                      <div className="space-y-4 text-xs leading-relaxed text-zinc-800">
                        <div className="border-t border-zinc-300 pt-3">
                          <h3 className="font-sans font-bold text-zinc-700 uppercase mb-1">1. Actividades Sospechosas Identificadas</h3>
                          <p>{caseDetails.rosReport.suspiciousActivities}</p>
                        </div>

                        <div className="border-t border-zinc-300 pt-3">
                          <h3 className="font-sans font-bold text-zinc-700 uppercase mb-1">2. Resumen Narrativo Detallado</h3>
                          <p>{caseDetails.rosReport.narrativeSummary}</p>
                        </div>

                        <div className="border-t border-zinc-300 pt-3">
                          <h3 className="font-sans font-bold text-zinc-700 uppercase mb-1">3. Medidas de Mitigación y Acciones Recomendadas</h3>
                          <p>{caseDetails.rosReport.recommendedActions}</p>
                        </div>
                      </div>

                      <div className="border-t-2 border-zinc-800 mt-10 pt-4 flex justify-between items-center text-[10px] font-mono text-zinc-500">
                        <span>Generado por Sentinel Swarm AI</span>
                        <span>Firma de Autoridad de Cumplimiento: ___________________</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 5: History / Timeline */}
                {activeCaseTab === "history" && (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Execution Timeline */}
                    <div className="lg:col-span-2 bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-4">
                      <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-850 pb-2">Timeline y Latencias de Procesamiento de Agentes</span>
                      <div className="relative border-l border-zinc-800 ml-4 pl-6 space-y-6">
                        {caseDetails.timeline.map((tm: any, idx: number) => (
                          <div key={idx} className="relative">
                            {/* Dot icon */}
                            <span className="absolute -left-[31px] top-0.5 w-4 h-4 rounded-full bg-zinc-950 border-2 border-emerald-500 flex items-center justify-center text-[8px] text-emerald-400 font-bold" />
                            <div className="text-xs font-mono">
                              <h5 className="font-bold text-zinc-200">{tm.event}</h5>
                              <div className="flex items-center gap-3 text-[10px] text-zinc-500 mt-1">
                                <span>{new Date(tm.timestamp).toLocaleTimeString()}</span>
                                <span>Latencia: <span className="text-emerald-500">{tm.latencyMs}ms</span></span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Audit Logs */}
                    <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-4">
                      <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-850 pb-2">Historial de Auditoría de Analistas (Audit Log)</span>
                      
                      <div className="space-y-4 overflow-y-auto max-h-[300px]">
                        {caseDetails.auditLogs?.map((log: any) => (
                          <div key={log.id} className="p-3 bg-zinc-950/60 rounded border border-zinc-850 text-[11px] font-mono space-y-1.5">
                            <div className="flex items-center justify-between text-zinc-400">
                              <span className="font-bold text-zinc-200">{log.user} ({log.role})</span>
                              <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
                            </div>
                            <div className="text-emerald-400 font-bold uppercase text-[9px]">{log.action}</div>
                            <p className="text-zinc-300 text-[10px]">{log.details}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

              </div>

              {/* PERSISTENT / STICKY DECISION PANEL - HUMAN ONLY */}
              <div className="border border-zinc-800 rounded-xl bg-zinc-900/40 p-5 mt-6 relative overflow-hidden">
                <div className="absolute right-0 top-0 w-24 h-24 bg-amber-500/1 rounded-full blur-2xl pointer-events-none" />

                <div className="flex items-center gap-2 border-b border-zinc-850 pb-2.5 mb-4">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-mono font-bold text-zinc-200 uppercase">Panel de Dictamen de Analista Compliance (Acción Humana Obligatoria)</span>
                </div>

                {activeRole === "Auditor" || activeRole === "Compliance Manager" ? (
                  <div className="p-4 bg-zinc-950/80 border border-zinc-850/50 rounded-lg flex items-center justify-center text-center gap-3">
                    <Lock className="w-5 h-5 text-zinc-600" />
                    <span className="text-xs font-mono text-zinc-500 max-w-lg">
                      Gated: El rol {activeRole} posee acceso estrictamente de LECTURA y no está autorizado a dictaminar o decidir sobre el expediente.
                    </span>
                  </div>
                ) : (
                  <form onSubmit={handleDecideCase} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    
                    {/* Action Select */}
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Seleccionar Resolución</label>
                      <select
                        value={decisionVerdict}
                        onChange={(e) => setDecisionVerdict(e.target.value as Verdict)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs font-mono text-zinc-300 focus:outline-none"
                      >
                        <option value={Verdict.BLOCK}>CONFIRM FRAUD (BLOCK)</option>
                        <option value={Verdict.ESCALATE}>ESCALAR (ESCALATE)</option>
                        <option value={Verdict.MONITOR}>MONITOREO CONTINUO (MONITOR)</option>
                        <option value={Verdict.DISCARD}>FALSE POSITIVE (DISCARD)</option>
                      </select>
                    </div>

                    {/* Comments Text */}
                    <div className="md:col-span-2 space-y-1.5">
                      <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Comentarios y Justificación de la Decisión</label>
                      <input
                        type="text"
                        required
                        value={decisionComments}
                        onChange={(e) => setDecisionComments(e.target.value)}
                        placeholder="ej. Confirmación de estructuración física de fondos hacia cuentas mulas de Chase Bank."
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none"
                      />
                    </div>

                    {/* Submit Button */}
                    <button
                      type="submit"
                      className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-600 text-zinc-950 rounded-lg font-mono font-bold text-xs transition uppercase cursor-pointer"
                    >
                      Guardar Decisión
                    </button>
                  </form>
                )}
              </div>

            </div>
          )}

          {/* 3. MANAGER DASHBOARD STAGE */}
          {currentView === "dashboard" && (
            <ManagerDashboard
              onSelectAlert={(caseId) => handleOpenCase(caseId)}
            />
          )}

          {/* 4. TENANT MANAGEMENT STAGE */}
          {currentView === "tenants" && (
            <TenantManagement />
          )}

          {/* 5. GRAPH EXPLORER STAGE */}
          {currentView === "graph-explorer" && (
            <GraphExplorerPage activeRole={activeRole} />
          )}

          {/* 6. SIMULATION/TESTING STAGE */}
          {currentView === "testing" && (
            <EventSubmissionTesting
              onCaseCreated={(caseId) => handleOpenCase(caseId)}
            />
          )}

        </div>
      </main>
    </div>
  );
}
