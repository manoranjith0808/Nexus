import React, { useState } from "react";
import { Database, UserCheck, Server, Activity, Plus, Trash2, ShieldCheck, Lock, Code, ArrowRight, Layers, HelpCircle, CheckCircle } from "lucide-react";
import { motion } from "motion/react";

interface DbUser {
  id: string;
  email: string;
  role: string;
  tenantId: string;
  tenantName: string;
  status: "Active" | "Suspended";
  clearanceLevel: "L1" | "L2" | "L3" | "SystemAdmin";
  lastLogin: string;
}

interface AuditLog {
  id: string;
  timestamp: string;
  userId: string;
  userEmail: string;
  action: string;
  tenantId: string;
  connectionRouted: string;
  status: "SUCCESS" | "DENIED";
}

export default function UserDbFlow() {
  const [dbUsers, setDbUsers] = useState<DbUser[]>([
    {
      id: "usr-001",
      email: "analyst@brou.com.uy",
      role: "Compliance Analyst (L1)",
      tenantId: "tenant-broU",
      tenantName: "Banco República (BROU)",
      status: "Active",
      clearanceLevel: "L1",
      lastLogin: "2026-07-16 08:30:11"
    },
    {
      id: "usr-002",
      email: "senior_analyst@bna.com.ar",
      role: "Senior Analyst (L2)",
      tenantId: "tenant-bnaAR",
      tenantName: "Banco de la Nación Argentina (BNA)",
      status: "Active",
      clearanceLevel: "L2",
      lastLogin: "2026-07-16 09:48:22"
    },
    {
      id: "usr-003",
      email: "manager@itau.com.uy",
      role: "Compliance Manager",
      tenantId: "tenant-itauUY",
      tenantName: "Banco Itaú Uruguay",
      status: "Active",
      clearanceLevel: "L2",
      lastLogin: "2026-07-15 15:28:44"
    },
    {
      id: "usr-004",
      email: "admin@nexus.com",
      role: "Platform Admin",
      tenantId: "global-nexus",
      tenantName: "Nexus Global System",
      status: "Active",
      clearanceLevel: "SystemAdmin",
      lastLogin: "2026-07-16 11:12:05"
    },
    {
      id: "usr-005",
      email: "auditor@bcu.gub.uy",
      role: "Regulatory Auditor",
      tenantId: "tenant-broU",
      tenantName: "Banco República (BROU)",
      status: "Active",
      clearanceLevel: "L1",
      lastLogin: "2026-07-14 10:05:12"
    }
  ]);

  const [dbLogs, setDbLogs] = useState<AuditLog[]>([
    {
      id: "log-101",
      timestamp: "2026-07-16 11:40:02",
      userId: "usr-001",
      userEmail: "analyst@brou.com.uy",
      action: "FETCH_ALERTS_QUEUE",
      tenantId: "tenant-broU",
      connectionRouted: "postgresql://brou_usr:***@localhost:5432/brou_compliance",
      status: "SUCCESS"
    },
    {
      id: "log-102",
      timestamp: "2026-07-16 11:41:15",
      userId: "usr-002",
      userEmail: "senior_analyst@bna.com.ar",
      action: "RESOLVE_CASE_BLOCK",
      tenantId: "tenant-bnaAR",
      connectionRouted: "postgresql://bna_usr:***@localhost:5432/bna_compliance",
      status: "SUCCESS"
    },
    {
      id: "log-103",
      timestamp: "2026-07-16 11:42:30",
      userId: "usr-003",
      userEmail: "manager@itau.com.uy",
      action: "EXPORT_DASHBOARD_KPIs",
      tenantId: "tenant-itauUY",
      connectionRouted: "postgresql://itau_usr:***@localhost:5432/itau_compliance",
      status: "SUCCESS"
    }
  ]);

  // Form states
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("Compliance Analyst (L1)");
  const [newTenant, setNewTenant] = useState("tenant-broU");
  const [newClearance, setNewClearance] = useState<"L1" | "L2" | "L3" | "SystemAdmin">("L1");

  // Flow Step Simulation
  const [simulationActive, setSimulationActive] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [simulationLogs, setSimulationLogs] = useState<string[]>([]);
  const [simulatingUser, setSimulatingUser] = useState<DbUser | null>(null);

  // SQL Query Input state
  const [sqlQuery, setSqlQuery] = useState("SELECT * FROM users WHERE status = 'Active';");
  const [sqlResult, setSqlResult] = useState<any[] | null>(null);

  const tenantMapping: Record<string, string> = {
    "tenant-broU": "Banco República (BROU)",
    "tenant-bnaAR": "Banco de la Nación Argentina (BNA)",
    "tenant-itauUY": "Banco Itaú Uruguay",
    "global-nexus": "Nexus Global System"
  };

  const executeSimulatedQuery = () => {
    const q = sqlQuery.trim().toLowerCase();
    let result: any[] = [];
    if (q.includes("select * from users") && q.includes("tenant-brou")) {
      result = dbUsers.filter(u => u.tenantId === "tenant-broU");
    } else if (q.includes("select * from users") && q.includes("active")) {
      result = dbUsers.filter(u => u.status === "Active");
    } else if (q.includes("select * from audit_logs") || q.includes("logs")) {
      result = dbLogs;
    } else if (q.includes("select * from users")) {
      result = dbUsers;
    } else {
      result = [{ message: "Empty set or unrecognized query syntax in demo console. Use 'SELECT * FROM users;' or 'SELECT * FROM users WHERE tenantId = 'tenant-broU';'" }];
    }
    setSqlResult(result);
  };

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim()) return;

    const addedUser: DbUser = {
      id: "usr-" + Date.now().toString().slice(-3),
      email: newEmail,
      role: newRole,
      tenantId: newTenant,
      tenantName: tenantMapping[newTenant],
      status: "Active",
      clearanceLevel: newClearance,
      lastLogin: new Date().toISOString().replace('T', ' ').slice(0, 19)
    };

    setDbUsers(prev => [...prev, addedUser]);
    setNewEmail("");

    // Create Audit Log
    const newLog: AuditLog = {
      id: "log-" + Date.now().toString().slice(-3),
      timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
      userId: "usr-admin",
      userEmail: "admin@nexus.com",
      action: `CREATE_USER_${addedUser.id}`,
      tenantId: "global-nexus",
      connectionRouted: "postgresql://nexus_master:***@localhost:5432/nexus_global_users",
      status: "SUCCESS"
    };
    setDbLogs(prev => [newLog, ...prev]);
  };

  const handleDeleteUser = (id: string) => {
    const usr = dbUsers.find(u => u.id === id);
    if (!usr) return;

    setDbUsers(prev => prev.filter(u => u.id !== id));

    // Log deletion
    const newLog: AuditLog = {
      id: "log-" + Date.now().toString().slice(-3),
      timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
      userId: "usr-admin",
      userEmail: "admin@nexus.com",
      action: `DELETE_USER_${id}`,
      tenantId: "global-nexus",
      connectionRouted: "postgresql://nexus_master:***@localhost:5432/nexus_global_users",
      status: "SUCCESS"
    };
    setDbLogs(prev => [newLog, ...prev]);
  };

  const triggerStepByStepSimulation = (user: DbUser) => {
    setSimulatingUser(user);
    setSimulationActive(true);
    setCurrentStep(1);
    setSimulationLogs(["[Init] Establishing connection sequence to user verification nodes..."]);

    setTimeout(() => {
      setCurrentStep(2);
      setSimulationLogs(prev => [
        ...prev,
        `[AUTH HANDSHAKE] Verified credentials for User: ${user.email}`,
        `[AUTH HANDSHAKE] User Identity resolved with ID: ${user.id} & Role: ${user.role}`
      ]);
    }, 1200);

    setTimeout(() => {
      setCurrentStep(3);
      const isGlobalAdmin = user.tenantId === "global-nexus";
      const pgUrl = isGlobalAdmin 
        ? "postgresql://nexus_master:***@localhost:5432/nexus_global_users"
        : `postgresql://${user.tenantId.split('-')[1]}_usr:***@localhost:5432/${user.tenantId.split('-')[1]}_compliance`;

      setSimulationLogs(prev => [
        ...prev,
        `[TENANT DISCOVERY] Security Context resolved to: ${user.tenantName}`,
        `[ROUTING] Dynamic DB Connection pool routed to schema url: "${pgUrl}"`,
        isGlobalAdmin 
          ? `[ROUTING] Global administrative access granted. Isolated connection bypassed.` 
          : `[ROUTING] Multi-tenant isolation verified. User cannot query tables from other banks.`
      ]);
    }, 2400);

    setTimeout(() => {
      setCurrentStep(4);
      setSimulationLogs(prev => [
        ...prev,
        `[RBAC ENFORCEMENT] Verified clearance permissions. Level: ${user.clearanceLevel}`,
        user.clearanceLevel === "L1" 
          ? `[RBAC] Compliance Analyst L1 constraints enabled (Read operations + Decision queue claiming only).`
          : user.clearanceLevel === "L2"
          ? `[RBAC] Compliance Analyst L2 privileges unlocked (Write operations + ROS Report generation + SOC automated responses).`
          : `[RBAC] System Admin/Auditor mode active. Full read/write or regulatory auditing unlocked.`
      ]);
    }, 3600);

    setTimeout(() => {
      setCurrentStep(5);
      // Push live audit log to state
      const simulatedLog: AuditLog = {
        id: "log-sim-" + Date.now().toString().slice(-3),
        timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
        userId: user.id,
        userEmail: user.email,
        action: "AUTHENTICATE_SESSION",
        tenantId: user.tenantId,
        connectionRouted: user.tenantId === "global-nexus" 
          ? "postgresql://nexus_master:***@localhost:5432/nexus_global_users" 
          : `postgresql://${user.tenantId.split('-')[1]}_usr:***@localhost:5432/${user.tenantId.split('-')[1]}_compliance`,
        status: "SUCCESS"
      };

      setDbLogs(prev => [simulatedLog, ...prev]);

      setSimulationLogs(prev => [
        ...prev,
        `[AUDIT LOGGED] Connection successfully persisted to centralized security audit ledger.`,
        `[SESSION STABLE] Handshake completed successfully. Token issued for 8 hours.`
      ]);
    }, 4800);
  };

  return (
    <div className="space-y-6">
      {/* Header Info Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 bg-zinc-900/40 p-4.5 rounded-xl border border-zinc-850">
        <div>
          <h2 className="text-sm font-mono font-bold text-zinc-200 uppercase tracking-wider">COMPLIANCE USER & TENANT DATABASE FLOW</h2>
          <p className="text-xs text-zinc-400 mt-0.5">Explore how bank compliance user accounts are stored, dynamically isolated, and audited under strict security frameworks.</p>
        </div>
        <div className="p-2 bg-zinc-950 border border-zinc-850 rounded text-[10px] font-mono text-emerald-400 flex items-center gap-1.5 shrink-0">
          <Database className="w-3.5 h-3.5" /> SECURE ISOLATION ENGINE ACTIVE
        </div>
      </div>

      {/* Database Schema & Dynamic Routing Architecture Visualization */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Schema Table 1: Users */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 space-y-3.5">
          <div className="flex items-center gap-2 border-b border-zinc-850 pb-2.5">
            <UserCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-mono font-bold text-zinc-200 uppercase">Schema: users Table</span>
          </div>
          <div className="font-mono text-[10px] text-zinc-400 space-y-1">
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span className="text-emerald-400">id</span> <span className="text-zinc-500">VARCHAR(64) PRIMARY KEY</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>email</span> <span className="text-zinc-500">VARCHAR(255) UNIQUE</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>password_hash</span> <span className="text-zinc-500">VARCHAR(255)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>role</span> <span className="text-zinc-500">VARCHAR(64)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span className="text-indigo-400">tenant_id</span> <span className="text-zinc-500">VARCHAR(64) REFERENCES tenants(id)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>clearance_level</span> <span className="text-zinc-500">VARCHAR(16)</span></div>
            <div className="flex justify-between"><span>status</span> <span className="text-zinc-500">VARCHAR(16) DEFAULT 'Active'</span></div>
          </div>
        </div>

        {/* Schema Table 2: Tenants */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 space-y-3.5">
          <div className="flex items-center gap-2 border-b border-zinc-850 pb-2.5">
            <Layers className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-mono font-bold text-zinc-200 uppercase">Schema: tenants Table</span>
          </div>
          <div className="font-mono text-[10px] text-zinc-400 space-y-1">
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span className="text-indigo-400">id</span> <span className="text-zinc-500">VARCHAR(64) PRIMARY KEY</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>name</span> <span className="text-zinc-500">VARCHAR(255)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>country</span> <span className="text-zinc-500">VARCHAR(4)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>regulatory_framework</span> <span className="text-zinc-500">VARCHAR(255)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>risk_threshold</span> <span className="text-zinc-500">NUMERIC(3,2)</span></div>
            <div className="flex justify-between"><span>db_connection_uri</span> <span className="text-zinc-500">VARCHAR(512) SECURE</span></div>
          </div>
        </div>

        {/* Schema Table 3: Audit Logs */}
        <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-4 space-y-3.5">
          <div className="flex items-center gap-2 border-b border-zinc-850 pb-2.5">
            <Activity className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-mono font-bold text-zinc-200 uppercase">Schema: audit_logs Table</span>
          </div>
          <div className="font-mono text-[10px] text-zinc-400 space-y-1">
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span className="text-amber-400">id</span> <span className="text-zinc-500">VARCHAR(64) PRIMARY KEY</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>timestamp</span> <span className="text-zinc-500">TIMESTAMP WITH TIME ZONE</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>user_id</span> <span className="text-zinc-500">VARCHAR(64) REFERENCES users(id)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>action</span> <span className="text-zinc-500">VARCHAR(64)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>tenant_id</span> <span className="text-zinc-500">VARCHAR(64) REFERENCES tenants(id)</span></div>
            <div className="flex justify-between border-b border-zinc-850 pb-1"><span>connection_routed</span> <span className="text-zinc-500">VARCHAR(512)</span></div>
            <div className="flex justify-between"><span>status</span> <span className="text-zinc-500">VARCHAR(16)</span></div>
          </div>
        </div>
      </div>

      {/* Step by Step Simulation Handshake Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Interactive Simulation Flow Triggers */}
        <div className="lg:col-span-1 bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-4">
          <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-850 pb-2">Simulate Database Handshake Sequence</span>
          <p className="text-xs text-zinc-400 font-mono">Select a compliance analyst registered below to run the live authentication, tenant database dynamic pool routing, and security audit log sequence:</p>
          
          <div className="space-y-2">
            {dbUsers.map(user => (
              <button
                key={user.id}
                onClick={() => triggerStepByStepSimulation(user)}
                className={`w-full p-2.5 rounded-lg border text-left text-xs font-mono transition flex items-center justify-between ${
                  simulatingUser?.id === user.id && simulationActive
                    ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400"
                    : "bg-zinc-950 border-zinc-850 hover:border-zinc-750 text-zinc-300"
                }`}
              >
                <div>
                  <span className="font-bold block">{user.email}</span>
                  <span className="text-[9px] text-zinc-500">{user.tenantName} ({user.clearanceLevel})</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-zinc-500" />
              </button>
            ))}
          </div>
        </div>

        {/* Live Sequence Flowchart */}
        <div className="lg:col-span-2 bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between">
          <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-850 pb-2">Active Session Handshake & Connection Isolation Router</span>
          
          {simulationActive && simulatingUser ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 py-4 relative">
              
              {/* Step 1 Box */}
              <div className={`p-3 rounded-lg border flex flex-col justify-between min-h-[110px] transition ${
                currentStep >= 2 ? "bg-emerald-500/5 border-emerald-500/40 text-emerald-400" : currentStep === 1 ? "bg-zinc-900 border-zinc-700 text-zinc-200" : "bg-zinc-950/50 border-zinc-900 text-zinc-600"
              }`}>
                <div className="text-[10px] font-mono font-bold uppercase">1. Auth Check</div>
                <div className="text-[11px] font-mono leading-tight my-1.5">{simulatingUser.email.split('@')[0]} credentials validation handshake</div>
                <div className="text-[9px] uppercase font-bold">{currentStep >= 2 ? "✓ PASSED" : currentStep === 1 ? "● IN PROGRESS" : "WAITING"}</div>
              </div>

              {/* Step 2 Box */}
              <div className={`p-3 rounded-lg border flex flex-col justify-between min-h-[110px] transition ${
                currentStep >= 3 ? "bg-emerald-500/5 border-emerald-500/40 text-emerald-400" : currentStep === 2 ? "bg-zinc-900 border-zinc-700 text-zinc-200" : "bg-zinc-950/50 border-zinc-900 text-zinc-600"
              }`}>
                <div className="text-[10px] font-mono font-bold uppercase">2. Route Tenant</div>
                <div className="text-[11px] font-mono leading-tight my-1.5">Map organization context to dynamic database node</div>
                <div className="text-[9px] uppercase font-bold">{currentStep >= 3 ? "✓ COMPLETED" : currentStep === 2 ? "● ROUTING POOL" : "WAITING"}</div>
              </div>

              {/* Step 3 Box */}
              <div className={`p-3 rounded-lg border flex flex-col justify-between min-h-[110px] transition ${
                currentStep >= 4 ? "bg-emerald-500/5 border-emerald-500/40 text-emerald-400" : currentStep === 3 ? "bg-zinc-900 border-zinc-700 text-zinc-200" : "bg-zinc-950/50 border-zinc-900 text-zinc-600"
              }`}>
                <div className="text-[10px] font-mono font-bold uppercase">3. RBAC Gate</div>
                <div className="text-[11px] font-mono leading-tight my-1.5">Verify clearance level ({simulatingUser.clearanceLevel}) for allowed endpoints</div>
                <div className="text-[9px] uppercase font-bold">{currentStep >= 4 ? "✓ ENFORCED" : currentStep === 3 ? "● CHECKING RBAC" : "WAITING"}</div>
              </div>

              {/* Step 4 Box */}
              <div className={`p-3 rounded-lg border flex flex-col justify-between min-h-[110px] transition ${
                currentStep >= 5 ? "bg-emerald-500/5 border-emerald-500/40 text-emerald-400" : currentStep === 4 ? "bg-zinc-900 border-zinc-700 text-zinc-200" : "bg-zinc-950/50 border-zinc-900 text-zinc-600"
              }`}>
                <div className="text-[10px] font-mono font-bold uppercase">4. Audit Trail</div>
                <div className="text-[11px] font-mono leading-tight my-1.5">Persist transaction log into immutable DB logging ledger</div>
                <div className="text-[9px] uppercase font-bold">{currentStep >= 5 ? "✓ PERSISTED" : currentStep === 4 ? "● WRITING LOG" : "WAITING"}</div>
              </div>

            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-zinc-500 font-mono text-xs">
              <Server className="w-8 h-8 text-zinc-700 mb-2" />
              <span>Click a compliance user on the left to simulate the isolated database flow sequence.</span>
            </div>
          )}

          {/* Simulation Output Logs Terminal */}
          <div className="bg-zinc-950/90 border border-zinc-850 rounded-lg p-3.5 font-mono text-[10px] text-zinc-400 min-h-[100px] flex flex-col justify-between">
            <span className="text-[9px] font-bold text-zinc-500 uppercase block mb-1.5">Live Connection Pool Logs Output:</span>
            <div className="space-y-1 max-h-[85px] overflow-y-auto">
              {simulationLogs.map((logLine, idx) => (
                <div key={idx} className={logLine.startsWith("[AUDIT") || logLine.startsWith("[Init") ? "text-emerald-400" : "text-zinc-300"}>
                  {logLine}
                </div>
              ))}
            </div>
            {simulationActive && currentStep === 5 && (
              <div className="text-[9px] text-emerald-500 font-bold border-t border-emerald-500/10 pt-1.5 mt-1 text-right flex items-center justify-end gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> SECURE SESSION TO COMPLIANCE DATABASE IS ACTIVE
              </div>
            )}
          </div>
        </div>

      </div>

      {/* SQL Query Console Simulator */}
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-850 pb-3">
          <h3 className="text-xs font-mono font-bold text-zinc-200 uppercase flex items-center gap-2">
            <Code className="w-4 h-4 text-emerald-400" /> PostgreSQL Multi-Tenant Query Console
          </h3>
          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500 border border-zinc-750">
            DEMO QUERY ENGINE
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Query Editor */}
          <div className="md:col-span-2 space-y-3">
            <div className="p-1 bg-zinc-950 rounded-lg border border-zinc-800">
              <div className="flex gap-2 p-1.5 border-b border-zinc-900">
                <button
                  onClick={() => setSqlQuery("SELECT * FROM users WHERE tenantId = 'tenant-broU';")}
                  className="text-[9px] font-mono text-zinc-500 hover:text-emerald-400 border border-zinc-850 px-2 py-0.5 rounded hover:bg-zinc-900"
                >
                  Query BROU users
                </button>
                <button
                  onClick={() => setSqlQuery("SELECT * FROM users WHERE status = 'Active';")}
                  className="text-[9px] font-mono text-zinc-500 hover:text-emerald-400 border border-zinc-850 px-2 py-0.5 rounded hover:bg-zinc-900"
                >
                  Query Active Users
                </button>
                <button
                  onClick={() => setSqlQuery("SELECT * FROM audit_logs ORDER BY timestamp DESC;")}
                  className="text-[9px] font-mono text-zinc-500 hover:text-emerald-400 border border-zinc-850 px-2 py-0.5 rounded hover:bg-zinc-900"
                >
                  Query Audit Logs
                </button>
              </div>
              <textarea
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                rows={3}
                className="w-full bg-transparent p-3 font-mono text-[11px] text-zinc-200 focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[9px] text-zinc-500 font-mono">
                * Test isolation policies: Row-Level Security (RLS) restricts access per Tenant ID.
              </span>
              <button
                onClick={executeSimulatedQuery}
                className="bg-emerald-500 hover:bg-emerald-600 text-zinc-950 px-4 py-2 rounded-lg font-mono font-bold text-xs transition cursor-pointer"
              >
                Execute Local Query
              </button>
            </div>
          </div>

          {/* Console Output Result */}
          <div className="bg-zinc-950 border border-zinc-850 rounded-lg p-4 flex flex-col justify-between overflow-x-auto min-h-[140px]">
            <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase block mb-2">Query Output Result</span>
            
            {sqlResult ? (
              <div className="flex-1 flex flex-col justify-between space-y-2">
                <div className="max-h-[95px] overflow-y-auto">
                  <pre className="text-[9px] font-mono text-zinc-300 leading-tight">
                    {JSON.stringify(sqlResult, null, 2)}
                  </pre>
                </div>
                <div className="text-[8px] text-zinc-500 border-t border-zinc-900 pt-1 text-right">
                  Query executed successfully: {sqlResult.length} rows returned.
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center text-zinc-600 font-mono text-[10px] py-4">
                <Database className="w-5 h-5 text-zinc-700 mb-1" />
                <span>Run a database query using the console controls.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* User DB Administration (CRUD table) */}
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-zinc-850 pb-3">
          <div>
            <h3 className="text-xs font-mono font-bold text-zinc-200 uppercase">Registered Compliance Users ({dbUsers.length})</h3>
            <p className="text-[10px] text-zinc-500 mt-0.5">Manage credentials, permissions, and multi-tenant security bindings for analysts.</p>
          </div>
        </div>

        {/* Form to Register Analyst */}
        <form onSubmit={handleCreateUser} className="bg-zinc-950/40 p-4 rounded-lg border border-zinc-850/60 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div className="space-y-1">
            <label className="text-[9px] font-mono font-bold text-zinc-500 uppercase">Analyst Email Address</label>
            <input
              type="email"
              required
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="e.g. j.doe@brou.com.uy"
              className="w-full bg-zinc-950 border border-zinc-850 focus:border-emerald-500/30 rounded-lg p-2 font-mono text-xs text-zinc-200 focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <label className="text-[9px] font-mono font-bold text-zinc-500 uppercase">Role Definition</label>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-850 rounded-lg p-2 font-mono text-xs text-zinc-300 focus:outline-none"
            >
              <option value="Compliance Analyst (L1)">Compliance Analyst (L1)</option>
              <option value="Senior Analyst (L2)">Senior Analyst (L2)</option>
              <option value="Compliance Manager">Compliance Manager</option>
              <option value="Regulatory Auditor">Regulatory Auditor</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[9px] font-mono font-bold text-zinc-500 uppercase">Tenant / Organization Binding</label>
            <select
              value={newTenant}
              onChange={(e) => setNewTenant(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-850 rounded-lg p-2 font-mono text-xs text-zinc-300 focus:outline-none"
            >
              <option value="tenant-broU">Banco República (BROU)</option>
              <option value="tenant-bnaAR">Banco de la Nación Argentina (BNA)</option>
              <option value="tenant-itauUY">Banco Itaú Uruguay</option>
              <option value="global-nexus">Platform Admin (Nexus)</option>
            </select>
          </div>

          <button
            type="submit"
            className="flex items-center justify-center gap-1 bg-emerald-500 hover:bg-emerald-600 text-zinc-950 rounded-lg font-mono font-bold text-xs p-2.5 transition cursor-pointer"
          >
            <Plus className="w-4 h-4" /> Add Compliance Analyst
          </button>
        </form>

        {/* Users Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs font-mono">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                <th className="py-2 px-3">User ID</th>
                <th className="py-2 px-3">Email Address</th>
                <th className="py-2 px-3">Role</th>
                <th className="py-2 px-3">Tenant Binding</th>
                <th className="py-2 px-3">Clearance</th>
                <th className="py-2 px-3">Last Active Login</th>
                <th className="py-2 px-3">Status</th>
                <th className="py-2 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-850 text-zinc-300">
              {dbUsers.map(user => (
                <tr key={user.id} className="hover:bg-zinc-950/20 transition">
                  <td className="py-3 px-3 font-bold text-emerald-400">{user.id}</td>
                  <td className="py-3 px-3 font-bold text-zinc-100">{user.email}</td>
                  <td className="py-3 px-3">{user.role}</td>
                  <td className="py-3 px-3 font-semibold text-indigo-400">{user.tenantName}</td>
                  <td className="py-3 px-3">
                    <span className="px-1.5 py-0.5 rounded bg-zinc-950 border border-zinc-850 text-zinc-400 text-[9px] font-bold">
                      {user.clearanceLevel}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-zinc-500">{user.lastLogin}</td>
                  <td className="py-3 px-3">
                    <span className="text-emerald-400 flex items-center gap-1 font-bold text-[10px]">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      {user.status}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right">
                    {user.id !== "usr-004" ? (
                      <button
                        onClick={() => handleDeleteUser(user.id)}
                        className="text-rose-400 hover:text-rose-300 transition cursor-pointer"
                        title="Delete analyst from User DB"
                      >
                        <Trash2 className="w-4 h-4 inline" />
                      </button>
                    ) : (
                      <span className="text-[9px] text-zinc-600 italic">Immutable</span>
                    )}
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
