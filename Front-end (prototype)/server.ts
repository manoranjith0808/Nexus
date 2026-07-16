import express from "express";
import path from "path";
import dotenv from "dotenv";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI } from "@google/genai";
import { Verdict, CaseStatus, PatternType, Alert, AgentReport, AuditLogEntry, NetworkGraph, Tenant, CaseDetails } from "./src/types.js";

dotenv.config();

const app = express();
app.use(express.json());

const PORT = 3000;

// Initialize Gemini Client safely
let ai: GoogleGenAI | null = null;
if (process.env.GEMINI_API_KEY && process.env.GEMINI_API_KEY !== "MY_GEMINI_API_KEY") {
  try {
    ai = new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        }
      }
    });
    console.log("Gemini client successfully initialized.");
  } catch (err) {
    console.error("Failed to initialize Gemini client:", err);
  }
} else {
  console.log("No GEMINI_API_KEY provided or it has default placeholder value. Running in Heuristic/Demo Mode.");
}

// Global In-Memory Store - English Localized
const tenants: Tenant[] = [
  {
    id: "tenant-broU",
    name: "Republic Bank of Uruguay (BROU)",
    country: "UY",
    regulatoryFramework: "BCU Circular 315/2022",
    riskThreshold: 0.65,
    createdAt: "2024-01-15T09:00:00Z"
  },
  {
    id: "tenant-itauUY",
    name: "Itaú Bank Uruguay",
    country: "UY",
    regulatoryFramework: "BCU AML/CFT Standards",
    riskThreshold: 0.70,
    createdAt: "2024-02-10T11:30:00Z"
  },
  {
    id: "tenant-bnaAR",
    name: "National Bank of Argentina (BNA)",
    country: "AR",
    regulatoryFramework: "UIF Resolution 14/2023",
    riskThreshold: 0.60,
    createdAt: "2024-03-01T08:00:00Z"
  }
];

const alerts: Alert[] = [
  {
    id: "case-001",
    caseId: "case-001",
    customerName: "Eduardo S. Rodríguez",
    customerDocument: "UY-CI 4.819.301-2",
    riskScore: 0.94,
    confidenceScore: 0.88,
    verdict: Verdict.BLOCK,
    status: CaseStatus.OPEN,
    country: "UY",
    tenantId: "tenant-broU",
    tenantName: "Republic Bank of Uruguay (BROU)",
    pattern: PatternType.SMURFING,
    amount: 14500,
    currency: "USD",
    timestamp: "2026-07-16T08:12:00-07:00",
    assignedTo: "analyst@brou.com.uy"
  },
  {
    id: "case-002",
    caseId: "case-002",
    customerName: "Sofía Martínez de Hoz",
    customerDocument: "AR-CUIT 27-35912405-9",
    riskScore: 0.81,
    confidenceScore: 0.75,
    verdict: Verdict.ESCALATE,
    status: CaseStatus.INVESTIGATING,
    country: "AR",
    tenantId: "tenant-bnaAR",
    tenantName: "National Bank of Argentina (BNA)",
    pattern: PatternType.ACCOUNT_TAKEOVER,
    amount: 2850000,
    currency: "ARS",
    timestamp: "2026-07-16T09:45:00-07:00",
    assignedTo: "analyst@bna.com.ar"
  },
  {
    id: "case-003",
    caseId: "case-003",
    customerName: "Carlos Almaraz Ortíz",
    customerDocument: "UY-CI 3.109.824-9",
    riskScore: 0.42,
    confidenceScore: 0.68,
    verdict: Verdict.DISCARD,
    status: CaseStatus.CLOSED,
    country: "UY",
    tenantId: "tenant-itauUY",
    tenantName: "Itaú Bank Uruguay",
    pattern: PatternType.SYNTHETIC_IDENTITY,
    amount: 1200,
    currency: "USD",
    timestamp: "2026-07-15T15:30:00-07:00",
    assignedTo: "manager@itau.com.uy"
  },
  {
    id: "case-004",
    caseId: "case-004",
    customerName: "Gabriela Lucía Bianchi",
    customerDocument: "AR-CUIT 23-28941032-4",
    riskScore: 0.72,
    confidenceScore: 0.82,
    verdict: Verdict.MONITOR,
    status: CaseStatus.OPEN,
    country: "AR",
    tenantId: "tenant-bnaAR",
    tenantName: "National Bank of Argentina (BNA)",
    pattern: PatternType.LAYERING,
    amount: 1800000,
    currency: "ARS",
    timestamp: "2026-07-16T04:22:00-07:00",
    assignedTo: null
  },
  {
    id: "case-005",
    caseId: "case-005",
    customerName: "Juan Manuel Salgueiro",
    customerDocument: "UY-CI 5.124.992-8",
    riskScore: 0.89,
    confidenceScore: 0.90,
    verdict: Verdict.BLOCK,
    status: CaseStatus.OPEN,
    country: "UY",
    tenantId: "tenant-broU",
    tenantName: "Republic Bank of Uruguay (BROU)",
    pattern: PatternType.ROUND_TRIPPING,
    amount: 98000,
    currency: "USD",
    timestamp: "2026-07-16T10:05:00-07:00",
    assignedTo: null
  },
  {
    id: "case-006",
    caseId: "case-006",
    customerName: "Valentina Solis Castro",
    customerDocument: "UY-CI 4.908.113-5",
    riskScore: 0.55,
    confidenceScore: 0.70,
    verdict: Verdict.MONITOR,
    status: CaseStatus.INVESTIGATING,
    country: "UY",
    tenantId: "tenant-itauUY",
    tenantName: "Itaú Bank Uruguay",
    pattern: PatternType.INSURANCE_FRAUD,
    amount: 8500,
    currency: "USD",
    timestamp: "2026-07-15T18:40:00-07:00",
    assignedTo: "analyst@itau.com.uy"
  },
  {
    id: "case-007",
    caseId: "case-007",
    customerName: "Mateo R. Fernández",
    customerDocument: "AR-CUIT 20-41098273-1",
    riskScore: 0.35,
    confidenceScore: 0.60,
    verdict: Verdict.DISCARD,
    status: CaseStatus.DECIDED,
    country: "AR",
    tenantId: "tenant-bnaAR",
    tenantName: "National Bank of Argentina (BNA)",
    pattern: PatternType.CARD_CAROUSEL,
    amount: 450000,
    currency: "ARS",
    timestamp: "2026-07-14T11:15:00-07:00",
    assignedTo: "senior_analyst@bna.com.ar"
  }
];

// In-Memory Narratives and Explanations - English Localized
const caseDetailsStore: Record<string, Partial<CaseDetails>> = {
  "case-001": {
    narrative: "Eduardo S. Rodríguez presented multiple structured deposits below the official regulatory reporting threshold (USD 10,000) across 5 different BROU branches in Montevideo within a 6-hour window. A total of USD 14,500 entered the account and was immediately wired to an offshore account in Miami. The customer's profile declares monthly income as an electrician of USD 1,200, which is completely inconsistent with these transaction volumes.",
    aiReasoning: [
      "Sentinel Swarm detected smurfing (structuring) via physical cash deposits across the BROU branch network.",
      "OSINT identified that the online banking access IP address corresponds to a TOR exit node registered in Germany, while the physical mobile device location corresponds to Montevideo.",
      "Historian matched the national document ID with a 2024 alert from Itaú Bank, categorized as an attempted fraud.",
      "The Jurist recommended BLOCK based on the absolute inconsistency of transaction history vs declared profile and rapid fund dispersal."
    ],
    timeline: [
      { event: "Suspicious transaction received at BROU", timestamp: "2026-07-16T08:12:00-07:00", latencyMs: 12 },
      { event: "Agent 1 Sentinel - Topology & Velocity analysis", timestamp: "2026-07-16T08:12:05-07:00", latencyMs: 4500 },
      { event: "Agent 2 OSINT - IP, VPN, and Phishing check", timestamp: "2026-07-16T08:12:08-07:00", latencyMs: 2300 },
      { event: "Agent 3 Patterns - Smurfing and Layering detection", timestamp: "2026-07-16T08:12:10-07:00", latencyMs: 1900 },
      { event: "Agent 4 Historian - RAG vector match", timestamp: "2026-07-16T08:12:11-07:00", latencyMs: 800 },
      { event: "Agent 5 Jurist - Recommendation & SAR generation", timestamp: "2026-07-16T08:12:14-07:00", latencyMs: 3200 },
      { event: "Case created and enqueued for analyst review", timestamp: "2026-07-16T08:12:15-07:00", latencyMs: 100 }
    ],
    rosReport: {
      subjectName: "Eduardo S. Rodríguez",
      documentType: "National Identity Card (UY)",
      documentNumber: "4.819.301-2",
      reportDate: "2026-07-16",
      suspiciousActivities: "Repetitive structured cash deposits across BROU teller desks to evade standard official reporting thresholds, followed by an immediate international wire transfer.",
      recommendedActions: "Temporarily block the originating account under Uruguay's Anti-Money Laundering Law 19,574. File a formal Suspicious Activity Report (SAR) with the Central Bank of Uruguay (BCU).",
      regulatoryCode: "BCU UY Circular 315/2022 Art. 4",
      narrativeSummary: "The subject structured USD 14,500 within 6 hours using geographically distributed tellers. Funds were unified in current account 203912/1 and transferred to CHASE BANK MIAMI. Inconsistent with client economic profile."
    },
    graph: {
      nodes: [
        { id: "Eduardo S. Rodríguez", label: "Eduardo S. Rodríguez (Target)", type: "account", val: 30, riskScore: 0.94 },
        { id: "BROU CC 203912/1", label: "Current Account UY", type: "account", val: 20, riskScore: 0.85 },
        { id: "Ventanilla Montevideo 1", label: "Ciudad Vieja Branch", type: "merchant", val: 15, riskScore: 0.2 },
        { id: "Ventanilla Montevideo 2", label: "Tres Cruces Branch", type: "merchant", val: 15, riskScore: 0.2 },
        { id: "Chase Bank Miami", label: "Chase Miami (Recipient)", type: "merchant", val: 25, riskScore: 0.75 },
        { id: "TOR IP: 185.220.101.4", label: "TOR Node IP (Germany)", type: "ip", val: 15, riskScore: 0.99 },
        { id: "Mobile Dev #9231", label: "iPhone 13 (Uruguay)", type: "device", val: 15, riskScore: 0.4 }
      ],
      links: [
        { source: "Ventanilla Montevideo 1", target: "BROU CC 203912/1", label: "Cash deposit USD 7,000" },
        { source: "Ventanilla Montevideo 2", target: "BROU CC 203912/1", label: "Cash deposit USD 7,500" },
        { source: "Eduardo S. Rodríguez", target: "BROU CC 203912/1", label: "Holder" },
        { source: "BROU CC 203912/1", target: "Chase Bank Miami", label: "International Wire USD 14,350" },
        { source: "Eduardo S. Rodríguez", target: "TOR IP: 185.220.101.4", label: "Web Login" },
        { source: "Eduardo S. Rodríguez", target: "Mobile Dev #9231", label: "App Auth" }
      ]
    },
    auditLogs: [
      { id: "audit-1", caseId: "case-001", timestamp: "2026-07-16T08:12:15-07:00", user: "System", role: "Swarm Coordinator", action: "Alert Triggered", details: "Case initialized and evaluated by Sentinel Swarm with an overall risk score of 0.94." },
      { id: "audit-2", caseId: "case-001", timestamp: "2026-07-16T08:30:00-07:00", user: "analyst@brou.com.uy", role: "Analyst L1", action: "Manual Assignment", details: "Analyst Eduardo claimed this case to begin the formal investigation." }
    ]
  },
  "case-002": {
    narrative: "Sofía Martínez de Hoz experienced a sudden change of email, phone number, and digital banking credentials within a 10-minute window from an unrecognized Android mobile device. Immediately after, she initiated 3 high-value transfers to new CBU accounts at Banco Galicia for a total of ARS 2,850,000, draining her savings account.",
    aiReasoning: [
      "Sentinel detected extreme geographical velocity: web login from Córdoba and App transfer from Rosario only 2 minutes apart.",
      "OSINT validated that the newly linked email address was registered less than 24 hours ago under a temporary Outlook domain.",
      "Patterns flagged high probability of Account Takeover (ATO) matching MITRE ATT&CK technique T1586.002 (User Account Compromise).",
      "The Jurist recommends immediate ESCALATE for expert human review before executing blocks that might cause customer friction."
    ],
    timeline: [
      { event: "BNA credential change alert", timestamp: "2026-07-16T09:43:00-07:00", latencyMs: 5 },
      { event: "Swarm Agent Analysis", timestamp: "2026-07-16T09:44:30-07:00", latencyMs: 90000 },
      { event: "Case created and enqueued", timestamp: "2026-07-16T09:45:00-07:00", latencyMs: 500 }
    ],
    rosReport: {
      subjectName: "Sofía Martínez de Hoz",
      documentType: "CUIT (AR)",
      documentNumber: "27-35912405-9",
      reportDate: "2026-07-16",
      suspiciousActivities: "Credential hijacking (Account Takeover), contact details modification, and rapid draining of deposits to external mule accounts.",
      recommendedActions: "Immediately freeze outbound transfer channels to mitigate financial loss. Contact the real holder via secondary analog phone line.",
      regulatoryCode: "UIF AR Res 14/2023 Sec II",
      narrativeSummary: "Authentication factor (2FA) changes observed from Telecom Argentina 4G mobile IP. ARS 2,850,000 transferred to mule accounts. Real customer currently unreachable."
    },
    graph: {
      nodes: [
        { id: "Sofía Martínez de Hoz", label: "Sofía Martínez de Hoz", type: "account", val: 25, riskScore: 0.81 },
        { id: "CBU BNA 192831", label: "BNA Savings Account (Compromised)", type: "account", val: 20, riskScore: 0.6 },
        { id: "Dispositivo Android Mule", label: "Moto G54 (Rosario)", type: "device", val: 18, riskScore: 0.95 },
        { id: "Dispositivo iOS Real", label: "iPhone 15 (Córdoba)", type: "device", val: 15, riskScore: 0.1 },
        { id: "Galicia Mulero 1", label: "CBU Galicia 007001", type: "account", val: 22, riskScore: 0.9 },
        { id: "Galicia Mulero 2", label: "CBU Galicia 007002", type: "account", val: 22, riskScore: 0.9 }
      ],
      links: [
        { source: "Sofía Martínez de Hoz", target: "CBU BNA 192831", label: "Holder" },
        { source: "CBU BNA 192831", target: "Dispositivo Android Mule", label: "New App Access" },
        { source: "CBU BNA 192831", target: "Dispositivo iOS Real", label: "Session Terminated" },
        { source: "CBU BNA 192831", target: "Galicia Mulero 1", label: "Transf. ARS 1,500,000" },
        { source: "CBU BNA 192831", target: "Galicia Mulero 2", label: "Transf. ARS 1,350,000" }
      ]
    },
    auditLogs: [
      { id: "audit-201", caseId: "case-002", timestamp: "2026-07-16T09:45:00-07:00", user: "System", role: "Swarm Coordinator", action: "Alert Triggered", details: "Alert generated for ATO suspicion with score 0.81" },
      { id: "audit-202", caseId: "case-002", timestamp: "2026-07-16T09:50:00-07:00", user: "analyst@bna.com.ar", role: "Analyst L1", action: "Automatic Assignment", details: "Case automatically assigned to analyst based on work queue load." }
    ]
  }
};

const agentReportsStore: Record<string, Record<string, AgentReport>> = {
  "case-001": {
    "1": {
      agentId: "1",
      agentName: "The Sentinel",
      caseId: "case-001",
      timestamp: "2026-07-16T08:12:05-07:00",
      riskScore: 0.92,
      confidence: 0.94,
      findings: [
        "Star structuring pattern (Smurfing Topology) detected with 2 coordinated concurrent incoming deposits.",
        "Transactional velocity anomaly: transaction frequency multiplied by 12x compared to last 180 days.",
        "Logins location mismatch: Browser geolocation reports Frankfurt, Germany (via commercial VPN), contrasting with physical cash deposits made in Montevideo branches within the same minutes."
      ],
      flags: ["CRITICAL_VELOCITY", "VPN_DETECTED", "LOCATION_MISMATCH"],
      evidence: {
        louvainCommunity: 12,
        betweennessCentrality: 0.89,
        impossibleTravelVelocity: "10,230 km/h (Frankfurt <-> Montevideo)"
      },
      recommendation: "BLOCK DIGITAL ACCESS and initiate biometric identity verification via secure channel.",
      latencyMs: 4500,
      isSimulated: false
    },
    "2": {
      agentId: "2",
      agentName: "OSINT Agent",
      caseId: "case-001",
      timestamp: "2026-07-16T08:12:08-07:00",
      riskScore: 0.88,
      confidence: 0.90,
      findings: [
        "IP verification: 185.220.101.4 categorized as a TOR exit node in IPQualityScore database.",
        "Authorizing mobile device corresponds to an Android Emulator (MEU_PLAY) instead of a physical smartphone.",
        "Analysis of email 'edu.rodriguez.elect@gmail.com' shows highly suspicious Google account creation age of only 5 days."
      ],
      flags: ["TOR_EXIT_NODE", "EMULATOR_DETECTED", "NEW_EMAIL_AGE"],
      evidence: {
        ipScore: 99,
        vpnStatus: "Active",
        torStatus: "Active",
        phishTankHit: false,
        redirectTrace: [
          "https://brou-secure-access.com",
          "https://brou-uy-login.net/login.php",
          "https://fraudulent-target-domain.com"
        ]
      },
      recommendation: "Reject cryptographic signatures issued by this device and require in-person branch verification.",
      latencyMs: 2300,
      isSimulated: false
    },
    "3": {
      agentId: "3",
      agentName: "Patterns Engine",
      caseId: "case-001",
      timestamp: "2026-07-16T08:12:10-07:00",
      riskScore: 0.95,
      confidence: 0.98,
      findings: [
        "Perfect match with regulatory pattern UY-SMURFING-A1.",
        "Cash structuring: Systematic deposits of USD 7,000 and USD 7,500 at branches less than 5km apart to evade reporting threshold of USD 10,000.",
        "The recipient Chase Bank account matches an international layering flow pattern."
      ],
      flags: ["REGULATORY_PATTERN_MATCH", "MONITORING_THRESHOLD_EVASION"],
      evidence: {
        patternName: "Montevideo Structuring",
        matchedRules: ["RULE-UY-315-E1", "RULE-UY-315-E3"],
        mitreAttackTags: ["T1586", "T1078.004"]
      },
      recommendation: "Suspend immediate international wire transfers and initiate administrative file for formal SAR reporting.",
      latencyMs: 1900,
      isSimulated: false
    },
    "4": {
      agentId: "4",
      agentName: "Historian Agent",
      caseId: "case-001",
      timestamp: "2026-07-16T08:12:11-07:00",
      riskScore: 0.70,
      confidence: 0.85,
      findings: [
        "RAG Store: 92% match on operational flow with closed fraud case '2025-UY-BROU-4410'.",
        "The client's national ID card has a partial match in external threat intelligence databases (AlienVault OTX).",
        "The current account owner has no direct laundering history, but destination offshore mule accounts have prior cyber fraud complaints."
      ],
      flags: ["RAG_STORE_MATCH", "THREAT_INTEL_DB_HIT"],
      evidence: {
        similarCases: [
          { caseId: "case-2025-4410", similarity: 0.92, outcome: "CONFIRMED_FRAUD" },
          { caseId: "case-2024-1102", similarity: 0.78, outcome: "FALSE_POSITIVE" }
        ],
        knownBadAddresses: ["Chase Bank AC #9213401"]
      },
      recommendation: "Temporarily freeze remaining balances on the originating account as a precaution.",
      latencyMs: 800,
      isSimulated: false
    },
    "5": {
      agentId: "5",
      agentName: "The Jurist",
      caseId: "case-001",
      timestamp: "2026-07-16T08:12:14-07:00",
      riskScore: 0.94,
      confidence: 0.92,
      findings: [
        "Regulatory evaluation: Clear breach of Art 4 of Central Bank of Uruguay Circular 315/2022 regarding cash flow justification.",
        "Sufficient evidence compiled to draft a Suspicious Activity Report (SAR).",
        "Sistemic suspicion level categorized as CRITICAL."
      ],
      flags: ["REGULATORY_NON_COMPLIANCE", "ROS_DRAFT_READY"],
      evidence: {
        legalFramework: "BCU Circular 315/2022",
        prosecutableArticles: ["Art 4.2 - Cash Control", "Art 7 - Due Diligence"],
        weightedConfScore: 0.912
      },
      recommendation: "BLOCK",
      latencyMs: 3200,
      isSimulated: false
    },
    "6": {
      agentId: "6",
      agentName: "Executor Agent",
      caseId: "case-001",
      timestamp: "2026-07-16T08:12:15-07:00",
      riskScore: 0.94,
      confidence: 0.90,
      findings: [
        "Executor agent compiled draft mitigation actions for the senior analyst.",
        "Action alert: Core banking direct freeze requires manual authorization under Uruguayan banking laws.",
        "Session termination and proxy greylisting of access IP completed."
      ],
      flags: ["SESSION_TERMINATED", "PROXY_GREYLISTED"],
      evidence: {
        actionsAvailable: [
          "Isolate client device",
          "Add IP to Firewall blocklist (TBAL)",
          "Trigger AV scan on channels",
          "Emit SAR Draft",
          "Freeze bank account (Requires manual Core auth)"
        ],
        actionsTaken: ["SESSION_TERMINATED", "PROXY_GREYLISTED"]
      },
      recommendation: "Request authorization for final core banking freeze.",
      latencyMs: 100,
      isSimulated: true
    }
  },
  "case-002": {
    "1": {
      agentId: "1",
      agentName: "The Sentinel",
      caseId: "case-002",
      timestamp: "2026-07-16T09:44:00-07:00",
      riskScore: 0.85,
      confidence: 0.80,
      findings: ["Extreme geographical velocity: Córdoba (Web Login) and Rosario (App Transfer) within 2 minutes."],
      flags: ["GEO_VELOCITY_ALARM"],
      evidence: { distance: "400km", timeframe: "120s" },
      recommendation: "Freeze digital channels as a precaution.",
      latencyMs: 3000,
      isSimulated: false
    },
    "2": {
      agentId: "2",
      agentName: "OSINT Agent",
      caseId: "case-002",
      timestamp: "2026-07-16T09:44:10-07:00",
      riskScore: 0.75,
      confidence: 0.70,
      findings: ["Temporary contact email detected."],
      flags: ["TEMPORARY_EMAIL_ADDRESS"],
      evidence: { domain: "temporary-outlook.com" },
      recommendation: "Verify identity via secure phone call to real holder.",
      latencyMs: 1500,
      isSimulated: false
    },
    "3": {
      agentId: "3",
      agentName: "Patterns Engine",
      caseId: "case-002",
      timestamp: "2026-07-16T09:44:15-07:00",
      riskScore: 0.90,
      confidence: 0.95,
      findings: ["Clear markers of account takeover."],
      flags: ["ACCOUNT_TAKEOVER_PATTERNS"],
      evidence: { mitreAttackTags: ["T1586.002"] },
      recommendation: "Escalate immediately with high priority.",
      latencyMs: 2000,
      isSimulated: false
    },
    "4": {
      agentId: "4",
      agentName: "Historian Agent",
      caseId: "case-002",
      timestamp: "2026-07-16T09:44:18-07:00",
      riskScore: 0.60,
      confidence: 0.70,
      findings: ["Target destination accounts are clean but newly registered (less than 72 hours)."],
      flags: ["NEW_MULE_ACCOUNTS"],
      evidence: { creationDate: "2026-07-13" },
      recommendation: "Block receiving channels.",
      latencyMs: 500,
      isSimulated: false
    },
    "5": {
      agentId: "5",
      agentName: "The Jurist",
      caseId: "case-002",
      timestamp: "2026-07-16T09:44:25-07:00",
      riskScore: 0.81,
      confidence: 0.85,
      findings: ["Major anomaly in standard high-volume outbound transfer behaviors."],
      flags: ["TRANSFERS_ANOMALOUS_VOLUME"],
      evidence: { limitBreached: "ARS 2,500,000 threshold" },
      recommendation: "ESCALATE",
      latencyMs: 2500,
      isSimulated: false
    },
    "6": {
      agentId: "6",
      agentName: "Executor Agent",
      caseId: "case-002",
      timestamp: "2026-07-16T09:44:30-07:00",
      riskScore: 0.81,
      confidence: 0.80,
      findings: ["Suggested SOC contingency action: temporarily deactivate app access."],
      flags: ["APP_DISABLED_RECOMMENDED"],
      evidence: {},
      recommendation: "Trigger app disablement flow.",
      latencyMs: 120,
      isSimulated: true
    }
  }
};

// Fill up defaults for other cases to prevent crashes
alerts.forEach(al => {
  if (al.id !== "case-001" && al.id !== "case-002") {
    caseDetailsStore[al.id] = {
      narrative: `Generic suspicion case of ${al.pattern} on client account belonging to ${al.customerName} (Document: ${al.customerDocument}). Value evaluated: ${al.currency} ${al.amount}.`,
      aiReasoning: [
        "Sentinel Swarm detected unusual activity spikes for this client profile.",
        "Historian found no matching direct historical fraud vectors.",
        "Patterns engine mapped a medium-high risk level for regional compliance."
      ],
      timeline: [
        { event: "Suspicious transaction received", timestamp: al.timestamp, latencyMs: 20 },
        { event: "Swarm Evaluation", timestamp: al.timestamp, latencyMs: 1200 },
        { event: "Alert generated", timestamp: al.timestamp, latencyMs: 50 }
      ],
      rosReport: {
        subjectName: al.customerName,
        documentType: "National Document",
        documentNumber: al.customerDocument,
        reportDate: "2026-07-16",
        suspiciousActivities: `Repetitive unusual movements mapped under pattern ${al.pattern}.`,
        recommendedActions: "Periodic monitoring and enhanced due diligence on fund origins.",
        regulatoryCode: al.country === "UY" ? "BCU Circular UY" : "UIF AR Res",
        narrativeSummary: `Unusual actions reported by ${al.pattern} for a total sum of ${al.currency} ${al.amount}.`
      },
      graph: {
        nodes: [
          { id: al.customerName, label: al.customerName, type: "account", val: 30, riskScore: al.riskScore },
          { id: "Banco Cuenta Principal", label: `Account ${al.tenantName}`, type: "account", val: 20, riskScore: al.riskScore * 0.8 },
          { id: "Nodo Externo Receptor", label: "Suspicious Recipient", type: "merchant", val: 22, riskScore: 0.5 },
          { id: "IP de Acceso", label: "IP 192.168.1.1", type: "ip", val: 15, riskScore: 0.3 }
        ],
        links: [
          { source: al.customerName, target: "Banco Cuenta Principal", label: "Holder" },
          { source: "Banco Cuenta Principal", target: "Nodo Externo Receptor", label: `Transfer ${al.currency} ${al.amount}` },
          { source: al.customerName, target: "IP de Acceso", label: "IP Access" }
        ]
      },
      auditLogs: [
        { id: `audit-${al.id}-1`, caseId: al.id, timestamp: al.timestamp, user: "System", role: "Swarm Coordinator", action: "Alert Triggered", details: `Alert initialized matching pattern ${al.pattern}.` }
      ]
    };

    agentReportsStore[al.id] = {
      "1": { agentId: "1", agentName: "The Sentinel", caseId: al.id, timestamp: al.timestamp, riskScore: al.riskScore, confidence: al.confidenceScore, findings: ["Unusual channel usage."], flags: ["INACTIVE_VELOCITY"], evidence: {}, recommendation: "MONITOR", latencyMs: 1200, isSimulated: false },
      "2": { agentId: "2", agentName: "OSINT Agent", caseId: al.id, timestamp: al.timestamp, riskScore: al.riskScore * 0.9, confidence: al.confidenceScore * 0.9, findings: ["Clean IP block but residential VPN signature."], flags: ["RESIDENTIAL_VPN"], evidence: {}, recommendation: "MONITOR", latencyMs: 900, isSimulated: false },
      "3": { agentId: "3", agentName: "Patterns Engine", caseId: al.id, timestamp: al.timestamp, riskScore: al.riskScore, confidence: al.confidenceScore, findings: ["Minor typological matches."], flags: ["LOW_LEVEL_SMURFING"], evidence: {}, recommendation: "MONITOR", latencyMs: 600, isSimulated: false },
      "4": { agentId: "4", agentName: "Historian Agent", caseId: al.id, timestamp: al.timestamp, riskScore: al.riskScore * 0.5, confidence: al.confidenceScore, findings: ["No previous direct fraud records found."], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 400, isSimulated: false },
      "5": { agentId: "5", agentName: "The Jurist", caseId: al.id, timestamp: al.timestamp, riskScore: al.riskScore, confidence: al.confidenceScore, findings: ["Medium level compliance alert markers."], flags: [], recommendation: "MONITOR", latencyMs: 1000, isSimulated: false },
      "6": { agentId: "6", agentName: "Executor Agent", caseId: al.id, timestamp: al.timestamp, riskScore: al.riskScore, confidence: al.confidenceScore, findings: ["Executor agent on standby."], flags: [], recommendation: "Standard Response", latencyMs: 90, isSimulated: true }
    };
  }
});

// API ROUTE HANDLERS

// 1. Alert Queue & Stats
app.get("/api/alerts/queue", (req, res) => {
  const { verdict, country, minScore, tenantId, status } = req.query;
  let filtered = [...alerts];

  if (verdict) filtered = filtered.filter(a => a.verdict === verdict);
  if (country) filtered = filtered.filter(a => a.country === country);
  if (tenantId) filtered = filtered.filter(a => a.tenantId === tenantId);
  if (status) filtered = filtered.filter(a => a.status === status);
  if (minScore) {
    const scoreVal = parseFloat(minScore as string);
    if (!isNaN(scoreVal)) {
      filtered = filtered.filter(a => a.riskScore >= scoreVal);
    }
  }

  // Sort by risk score descending by default
  filtered.sort((a, b) => b.riskScore - a.riskScore);

  res.json(filtered);
});

app.get("/api/alerts/queue/stats", (req, res) => {
  const pending = alerts.filter(a => a.status === CaseStatus.OPEN || a.status === CaseStatus.INVESTIGATING).length;
  const critical = alerts.filter(a => a.riskScore >= 0.8 && a.status !== CaseStatus.CLOSED).length;
  const total = alerts.length;
  const resolved = alerts.filter(a => a.status === CaseStatus.CLOSED || a.status === CaseStatus.DECIDED || a.status === CaseStatus.EXECUTED).length;

  res.json({
    pending,
    critical,
    total,
    resolved
  });
});

app.post("/api/alerts/:case_id/assign", (req, res) => {
  const { case_id } = req.params;
  const { analystName } = req.body;
  const alert = alerts.find(a => a.id === case_id);

  if (!alert) {
    return res.status(404).json({ error: "Case not found" });
  }

  alert.assignedTo = analystName || "analyst@nexus.com";
  alert.status = CaseStatus.INVESTIGATING;

  // Add to audit log
  const detail = caseDetailsStore[case_id];
  if (detail) {
    const newLog: AuditLogEntry = {
      id: "audit-" + Date.now(),
      caseId: case_id,
      timestamp: new Date().toISOString(),
      user: analystName || "analyst@nexus.com",
      role: "Analyst",
      action: "Manual Assignment",
      details: `Case claimed by ${analystName || "analyst@nexus.com"} to initiate investigation.`
    };
    detail.auditLogs = [newLog, ...(detail.auditLogs || [])];
  }

  res.json({ success: true, alert });
});

// 2. Case View Details
app.get("/api/alerts/:case_id", (req, res) => {
  const { case_id } = req.params;
  const alert = alerts.find(a => a.id === case_id);
  if (!alert) {
    return res.status(404).json({ error: "Alert not found" });
  }
  res.json(alert);
});

app.get("/api/cases/:id", (req, res) => {
  const { id } = req.params;
  const alert = alerts.find(a => a.id === id);
  const details = caseDetailsStore[id];

  if (!alert || !details) {
    return res.status(404).json({ error: "Case not found" });
  }

  res.json({
    id,
    alert,
    ...details
  });
});

app.get("/api/reports/:case_id/narrative", (req, res) => {
  const { case_id } = req.params;
  const details = caseDetailsStore[case_id];
  if (!details) {
    return res.status(404).json({ error: "Case details not found" });
  }
  res.json({ narrative: details.narrative });
});

app.get("/api/cases/:id/agents/:agent", (req, res) => {
  const { id, agent } = req.params;
  const reports = agentReportsStore[id];
  if (!reports) {
    return res.status(404).json({ error: "No agent reports found for this case" });
  }
  const report = reports[agent];
  if (!report) {
    return res.status(404).json({ error: `Agent ${agent} report not found` });
  }
  res.json(report);
});

app.get("/api/cases/:id/timeline", (req, res) => {
  const { id } = req.params;
  const details = caseDetailsStore[id];
  if (!details) {
    return res.status(404).json({ error: "Case timeline not found" });
  }
  res.json(details.timeline || []);
});

app.get("/api/graph/:tid/subgraph/:node", (req, res) => {
  const { node } = req.params;
  const detail = Object.values(caseDetailsStore).find(d => 
    d.graph?.nodes.some(n => n.id.toLowerCase().includes(node.toLowerCase()))
  ) || caseDetailsStore["case-001"];

  res.json(detail.graph || { nodes: [], links: [] });
});

app.get("/api/graph/:tid/full", (req, res) => {
  const { tid } = req.params;
  const tenantAlerts = alerts.filter(a => a.tenantId === tid);
  const nodesMap = new Map();
  const links: any[] = [];

  tenantAlerts.forEach(a => {
    const detail = caseDetailsStore[a.id];
    if (detail && detail.graph) {
      detail.graph.nodes.forEach(n => {
        nodesMap.set(n.id, { ...n, val: Math.max(n.val, nodesMap.get(n.id)?.val || 0) });
      });
      detail.graph.links.forEach(l => {
        links.push(l);
      });
    }
  });

  res.json({
    nodes: Array.from(nodesMap.values()),
    links: links.filter((l, index, self) =>
      self.findIndex(other => other.source === l.source && other.target === l.target) === index
    )
  });
});

app.get("/api/reports/:case_id/ros", (req, res) => {
  const { case_id } = req.params;
  const details = caseDetailsStore[case_id];
  if (!details) {
    return res.status(404).json({ error: "Case ROS report not found" });
  }
  res.json(details.rosReport);
});

app.post("/api/alerts/:case_id/decide", (req, res) => {
  const { case_id } = req.params;
  const { verdict, comments, analystName, analystRole } = req.body;
  const alert = alerts.find(a => a.id === case_id);

  if (!alert) {
    return res.status(404).json({ error: "Case not found" });
  }

  alert.verdict = verdict;
  alert.status = CaseStatus.DECIDED;

  // Add to audit log
  const detail = caseDetailsStore[case_id];
  if (detail) {
    const newLog: AuditLogEntry = {
      id: "audit-" + Date.now(),
      caseId: case_id,
      timestamp: new Date().toISOString(),
      user: analystName || "analyst@nexus.com",
      role: analystRole || "Analyst L1",
      action: `Decision Resolved: ${verdict}`,
      details: comments || `Analyst resolved to catalogue the case as ${verdict}.`
    };
    detail.auditLogs = [newLog, ...(detail.auditLogs || [])];
  }

  res.json({ success: true, alert });
});

// 3. Metrics & Stats
app.get("/api/cases/stats/summary", (req, res) => {
  const verdictDistribution = [
    { name: "BLOCK", value: alerts.filter(a => a.verdict === Verdict.BLOCK).length, color: "#ef4444" },
    { name: "ESCALATE", value: alerts.filter(a => a.verdict === Verdict.ESCALATE).length, color: "#f97316" },
    { name: "MONITOR", value: alerts.filter(a => a.verdict === Verdict.MONITOR).length, color: "#eab308" },
    { name: "DISCARD", value: alerts.filter(a => a.verdict === Verdict.DISCARD).length, color: "#10b981" }
  ];

  const patternDistribution = [
    { name: "Smurfing", value: alerts.filter(a => a.pattern === PatternType.SMURFING).length },
    { name: "Account Takeover", value: alerts.filter(a => a.pattern === PatternType.ACCOUNT_TAKEOVER).length },
    { name: "Synt. Identity", value: alerts.filter(a => a.pattern === PatternType.SYNTHETIC_IDENTITY).length },
    { name: "Layering", value: alerts.filter(a => a.pattern === PatternType.LAYERING).length },
    { name: "Insurance Fraud", value: alerts.filter(a => a.pattern === PatternType.INSURANCE_FRAUD).length },
    { name: "Card Carousel", value: alerts.filter(a => a.pattern === PatternType.CARD_CAROUSEL).length },
    { name: "Round Tripping", value: alerts.filter(a => a.pattern === PatternType.ROUND_TRIPPING).length }
  ];

  const kpis = {
    averageRiskScore: parseFloat((alerts.reduce((acc, a) => acc + a.riskScore, 0) / alerts.length).toFixed(2)),
    averageConfidence: parseFloat((alerts.reduce((acc, a) => acc + a.confidenceScore, 0) / alerts.length).toFixed(2)),
    totalAmountsUSD: alerts.reduce((acc, a) => {
      const amtUSD = a.currency === "ARS" ? a.amount / 900 : a.amount;
      return acc + amtUSD;
    }, 0),
    alertsProcessedLast24h: alerts.length
  };

  const trendData = [
    { date: "Jul 10", alerts: 3, critical: 1, amountK: 45 },
    { date: "Jul 11", alerts: 4, critical: 2, amountK: 80 },
    { date: "Jul 12", alerts: 5, critical: 1, amountK: 65 },
    { date: "Jul 13", alerts: 8, critical: 3, amountK: 120 },
    { date: "Jul 14", alerts: 6, critical: 2, amountK: 95 },
    { date: "Jul 15", alerts: 11, critical: 5, amountK: 190 },
    { date: "Jul 16", alerts: alerts.length, critical: alerts.filter(a => a.riskScore >= 0.8).length, amountK: Math.round(kpis.totalAmountsUSD / 1000) }
  ];

  res.json({
    verdictDistribution,
    patternDistribution,
    kpis,
    trendData
  });
});

app.get("/api/tenants/:id/stats", (req, res) => {
  const { id } = req.params;
  const tenantAlerts = alerts.filter(a => a.tenantId === id);
  const total = tenantAlerts.length;
  const critical = tenantAlerts.filter(a => a.riskScore >= 0.8).length;
  const avgRisk = total > 0 ? parseFloat((tenantAlerts.reduce((acc, a) => acc + a.riskScore, 0) / total).toFixed(2)) : 0;

  res.json({
    tenantId: id,
    totalAlerts: total,
    criticalAlerts: critical,
    averageRiskScore: avgRisk,
    distribution: [
      { name: "BLOCK", value: tenantAlerts.filter(a => a.verdict === Verdict.BLOCK).length },
      { name: "ESCALATE", value: tenantAlerts.filter(a => a.verdict === Verdict.ESCALATE).length },
      { name: "MONITOR", value: tenantAlerts.filter(a => a.verdict === Verdict.MONITOR).length },
      { name: "DISCARD", value: tenantAlerts.filter(a => a.verdict === Verdict.DISCARD).length }
    ]
  });
});

// 4. CRUD Tenants
app.get("/api/tenants", (req, res) => {
  res.json(tenants);
});

app.post("/api/tenants", (req, res) => {
  const { name, country, regulatoryFramework, riskThreshold } = req.body;
  if (!name || !country) {
    return res.status(400).json({ error: "Name and country are required." });
  }

  const newTenant: Tenant = {
    id: "tenant-" + Date.now(),
    name,
    country,
    regulatoryFramework: regulatoryFramework || "Standard BCU/UIF Normative",
    riskThreshold: typeof riskThreshold === "number" ? riskThreshold : 0.65,
    createdAt: new Date().toISOString()
  };

  tenants.push(newTenant);
  res.status(201).json(newTenant);
});

app.put("/api/tenants/:id", (req, res) => {
  const { id } = req.params;
  const { name, country, regulatoryFramework, riskThreshold } = req.body;
  const idx = tenants.findIndex(t => t.id === id);

  if (idx === -1) {
    return res.status(404).json({ error: "Tenant not found" });
  }

  tenants[idx] = {
    ...tenants[idx],
    name: name || tenants[idx].name,
    country: country || tenants[idx].country,
    regulatoryFramework: regulatoryFramework || tenants[idx].regulatoryFramework,
    riskThreshold: typeof riskThreshold === "number" ? riskThreshold : tenants[idx].riskThreshold
  };

  res.json(tenants[idx]);
});

app.delete("/api/tenants/:id", (req, res) => {
  const { id } = req.params;
  const idx = tenants.findIndex(t => t.id === id);
  if (idx === -1) {
    return res.status(404).json({ error: "Tenant not found" });
  }
  tenants.splice(idx, 1);
  res.json({ success: true });
});

// 5. Manual and Bulk Event processing
app.post("/api/events/process", async (req, res) => {
  const { customerName, customerDocument, tenantId, amount, currency, pattern, remarks } = req.body;

  if (!customerName || !customerDocument || !tenantId || !amount || !pattern) {
    return res.status(400).json({ error: "Missing required event fields." });
  }

  const selectedTenant = tenants.find(t => t.id === tenantId) || tenants[0];
  const caseId = "case-" + (alerts.length + 1).toString().padStart(3, '0');
  const riskScore = parseFloat((0.6 + Math.random() * 0.38).toFixed(2));
  const confidenceScore = parseFloat((0.7 + Math.random() * 0.25).toFixed(2));

  let generatedNarrative = "";
  let steps: string[] = [];
  let generatedRos: any = null;

  // Utilize GEMINI API IF INSTANTIATED
  if (ai) {
    try {
      console.log(`Generating AI Narrative for case: ${caseId} via Gemini...`);
      const response = await ai.models.generateContent({
        model: "gemini-2.5-flash",
        contents: `Analyze this banking fraud alert transaction and generate:
1. A short, professional narrative description in English of how the fraud was executed.
2. 4 specific analytical steps taken by the Swarm agents to uncover the fraud.
3. A summary of a formal suspicious activity report (SAR).

Case parameters:
- Client: ${customerName} (Document: ${customerDocument})
- Bank: ${selectedTenant.name} (${selectedTenant.country})
- Amount: ${currency || "USD"} ${amount}
- Pattern: ${pattern}
- Additional comments from agent: ${remarks || "None"}

Required output format: Pure JSON structured as:
{
  "narrative": "...",
  "reasoningSteps": ["Step 1...", "Step 2...", "Step 3...", "Step 4..."],
  "rosSuspiciousActivities": "...",
  "rosRecommendedActions": "...",
  "rosSummary": "..."
}`,
        config: {
          responseMimeType: "application/json"
        }
      });

      const parsed = JSON.parse(response.text?.trim() || "{}");
      generatedNarrative = parsed.narrative || "";
      steps = parsed.reasoningSteps || [];
      generatedRos = {
        suspiciousActivities: parsed.rosSuspiciousActivities || "",
        recommendedActions: parsed.rosRecommendedActions || "",
        narrativeSummary: parsed.rosSummary || ""
      };
    } catch (err) {
      console.error("Gemini Generation failed, falling back to heuristics:", err);
    }
  }

  // Fallbacks if Gemini was not available or failed
  if (!generatedNarrative) {
    generatedNarrative = `The compliance officer reported suspicious behavior in the account of ${customerName}. A direct correlation was observed with ${pattern} typologies totaling ${currency || "USD"} ${amount}. The document ${customerDocument} displays active alarms in the integrated security network. ${remarks || ""}`;
  }
  if (!steps.length) {
    steps = [
      `Sentinel Swarm identified spikes of unusual transaction behaviors corresponding to ${pattern}.`,
      `The OSINT engine scanned the relevated IP activity and determined matches with high-risk connections.`,
      `Historian localized behavior matches with 85% vector similarity in the historic fraud storage.`,
      `The Jurist consolidated evidence and initiated draft report compilation with a calculated risk score of ${Math.round(riskScore * 100)}%.`
    ];
  }
  if (!generatedRos) {
    generatedRos = {
      suspiciousActivities: `Unusual structured movements or deposits of funds mapped under the ${pattern} pattern for ${currency || "USD"} ${amount}.`,
      recommendedActions: `Immediately notify national regulatory authorities in ${selectedTenant.country} and temporarily block transactions exceeding safety thresholds.`,
      narrativeSummary: `Observed repetitive anomalous behavior from account holder ${customerName} (Doc: ${customerDocument}) that evades standard banking operations and suggests laundering activity.`
    };
  }

  const newAlert: Alert = {
    id: caseId,
    caseId,
    customerName,
    customerDocument,
    riskScore,
    confidenceScore,
    verdict: riskScore >= 0.8 ? Verdict.BLOCK : Verdict.MONITOR,
    status: CaseStatus.OPEN,
    country: selectedTenant.country,
    tenantId: selectedTenant.id,
    tenantName: selectedTenant.name,
    pattern: pattern as PatternType,
    amount: parseFloat(amount),
    currency: currency || "USD",
    timestamp: new Date().toISOString(),
    assignedTo: null
  };

  alerts.unshift(newAlert);

  caseDetailsStore[caseId] = {
    narrative: generatedNarrative,
    aiReasoning: steps,
    timeline: [
      { event: "Transaction queued", timestamp: new Date().toISOString(), latencyMs: 15 },
      { event: "Sentinel Swarm Evaluator", timestamp: new Date().toISOString(), latencyMs: 2500 },
      { event: "SAR Draft Generated", timestamp: new Date().toISOString(), latencyMs: 1100 }
    ],
    rosReport: {
      subjectName: customerName,
      documentType: selectedTenant.country === "UY" ? "CI (Uruguay)" : "CUIT (Argentina)",
      documentNumber: customerDocument,
      reportDate: new Date().toISOString().split('T')[0],
      suspiciousActivities: generatedRos.suspiciousActivities,
      recommendedActions: generatedRos.recommendedActions,
      regulatoryCode: selectedTenant.country === "UY" ? "BCU Circular 315" : "UIF Res 14/2023",
      narrativeSummary: generatedRos.narrativeSummary
    },
    graph: {
      nodes: [
        { id: customerName, label: `${customerName} (Target)`, type: "account", val: 30, riskScore },
        { id: "Banco Cuenta Principal", label: `Account ${selectedTenant.name}`, type: "account", val: 20, riskScore: riskScore * 0.8 },
        { id: "Canal Digital", label: "IP " + (Math.random() > 0.5 ? "181.29.1.55" : "200.40.10.12"), type: "ip", val: 15, riskScore: 0.4 },
        { id: "Cuenta Destino Mule", label: "CBU Receiver 11029", type: "account", val: 22, riskScore: 0.7 }
      ],
      links: [
        { source: customerName, target: "Banco Cuenta Principal", label: "Holder" },
        { source: customerName, target: "Canal Digital", label: "IP Access" },
        { source: "Banco Cuenta Principal", target: "Cuenta Destino Mule", label: `Transfer ${currency || "USD"} ${amount}` }
      ]
    },
    auditLogs: [
      { id: "audit-" + Date.now(), caseId, timestamp: new Date().toISOString(), user: "System", role: "Swarm Coordinator", action: "Alert Created", details: `Case manually submitted. Swarm risk score calculated at: ${riskScore}.` }
    ]
  };

  // Preseed agent reports for this new case
  agentReportsStore[caseId] = {
    "1": { agentId: "1", agentName: "The Sentinel", caseId, timestamp: new Date().toISOString(), riskScore: riskScore, confidence: confidenceScore, findings: [steps[0]], flags: ["MANUAL_ENTRY_TRIGGER"], evidence: {}, recommendation: "MONITOR", latencyMs: 2500, isSimulated: false },
    "2": { agentId: "2", agentName: "OSINT Agent", caseId, timestamp: new Date().toISOString(), riskScore: riskScore * 0.9, confidence: confidenceScore * 0.8, findings: [steps[1]], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 1400, isSimulated: false },
    "3": { agentId: "3", agentName: "Patterns Engine", caseId, timestamp: new Date().toISOString(), riskScore: riskScore, confidence: confidenceScore * 0.95, findings: [steps[2]], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 1000, isSimulated: false },
    "4": { agentId: "4", agentName: "Historian Agent", caseId, timestamp: new Date().toISOString(), riskScore: riskScore * 0.6, confidence: confidenceScore, findings: ["RAG database successfully scanned for document connection logs."], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 600, isSimulated: false },
    "5": { agentId: "5", agentName: "The Jurist", caseId, timestamp: new Date().toISOString(), riskScore: riskScore, confidence: confidenceScore, findings: [steps[3]], flags: [], recommendation: riskScore >= 0.8 ? "BLOCK" : "MONITOR", latencyMs: 1200, isSimulated: false },
    "6": { agentId: "6", agentName: "Executor Agent", caseId, timestamp: new Date().toISOString(), riskScore: riskScore, confidence: confidenceScore, findings: ["Reactive emergency mitigations prepared on manual queue."], flags: [], recommendation: "Emergency Response", latencyMs: 80, isSimulated: true }
  };

  res.status(201).json({ success: true, caseId, alert: newAlert });
});

app.post("/api/events/process/bulk", (req, res) => {
  const { events } = req.body;
  if (!events || !Array.isArray(events)) {
    return res.status(400).json({ error: "Events array is required." });
  }

  const processedIds: string[] = [];
  events.forEach((ev: any) => {
    const customerName = ev.customerName || "Unknown Customer";
    const customerDocument = ev.customerDocument || "UY-CI 0000000-0";
    const tenantId = ev.tenantId || tenants[0].id;
    const selectedTenant = tenants.find(t => t.id === tenantId) || tenants[0];
    const caseId = "case-" + (alerts.length + 1).toString().padStart(3, '0');
    const amount = parseFloat(ev.amount || 5000);
    const currency = ev.currency || "USD";
    const pattern = ev.pattern || PatternType.SMURFING;
    const riskScore = parseFloat((0.5 + Math.random() * 0.45).toFixed(2));
    const confidenceScore = parseFloat((0.6 + Math.random() * 0.35).toFixed(2));

    const newAlert: Alert = {
      id: caseId,
      caseId,
      customerName,
      customerDocument,
      riskScore,
      confidenceScore,
      verdict: riskScore >= 0.8 ? Verdict.BLOCK : Verdict.MONITOR,
      status: CaseStatus.OPEN,
      country: selectedTenant.country,
      tenantId: selectedTenant.id,
      tenantName: selectedTenant.name,
      pattern: pattern as PatternType,
      amount,
      currency,
      timestamp: new Date().toISOString(),
      assignedTo: null
    };

    alerts.unshift(newAlert);
    processedIds.push(caseId);

    // Seed default structures
    caseDetailsStore[caseId] = {
      narrative: `Bulk Import: Fraud suspicion alert for pattern ${pattern} detected in client profile ${customerName}.`,
      aiReasoning: [`Bulk transaction block successfully processed and checked by Swarm.`],
      timeline: [{ event: "Bulk file import processing", timestamp: new Date().toISOString(), latencyMs: 10 }],
      rosReport: {
        subjectName: customerName,
        documentType: "National Document",
        documentNumber: customerDocument,
        reportDate: new Date().toISOString().split('T')[0],
        suspiciousActivities: `Mass ingestion of transactions valued at ${currency} ${amount}.`,
        recommendedActions: "Verify physical credentials in secure channels.",
        regulatoryCode: "Bulk-Load",
        narrativeSummary: `Bulk import transaction logs.`
      },
      graph: {
        nodes: [{ id: customerName, label: customerName, type: "account", val: 30, riskScore }],
        links: []
      },
      auditLogs: [{ id: "audit-" + Date.now(), caseId, timestamp: new Date().toISOString(), user: "Bulk Loader", role: "Admin", action: "Importation", details: "Case instantiated from external JSON bulk payload." }]
    };

    agentReportsStore[caseId] = {
      "1": { agentId: "1", agentName: "The Sentinel", caseId, timestamp: new Date().toISOString(), riskScore, confidence: confidenceScore, findings: [], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 50, isSimulated: true },
      "2": { agentId: "2", agentName: "OSINT Agent", caseId, timestamp: new Date().toISOString(), riskScore, confidence: confidenceScore, findings: [], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 50, isSimulated: true },
      "3": { agentId: "3", agentName: "Patterns Engine", caseId, timestamp: new Date().toISOString(), riskScore, confidence: confidenceScore, findings: [], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 50, isSimulated: true },
      "4": { agentId: "4", agentName: "Historian Agent", caseId, timestamp: new Date().toISOString(), riskScore, confidence: confidenceScore, findings: [], flags: [], evidence: {}, recommendation: "MONITOR", latencyMs: 50, isSimulated: true },
      "5": { agentId: "5", agentName: "The Jurist", caseId, timestamp: new Date().toISOString(), riskScore, confidence: confidenceScore, findings: [], recommendation: "MONITOR", latencyMs: 50, isSimulated: true },
      "6": { agentId: "6", agentName: "Executor Agent", caseId, timestamp: new Date().toISOString(), riskScore, confidence: confidenceScore, findings: [], recommendation: "Standby", latencyMs: 50, isSimulated: true }
    };
  });

  res.json({ success: true, processedCount: processedIds.length, processedIds });
});

// Cypher console raw mock execution surface
app.post("/api/graph/:tid/query", (req, res) => {
  const { query } = req.body;
  if (!query) {
    return res.status(400).json({ error: "Cypher query is required" });
  }

  const normalized = query.toLowerCase();
  let columns: string[] = ["NodeName", "RiskScore", "FraudType", "ConnectionCount"];
  let rows: any[] = [];

  if (normalized.includes("match") && normalized.includes("sentinel")) {
    rows = [
      ["Eduardo S. Rodríguez", "0.94", "SMURFING", "5"],
      ["Sofía Martínez de Hoz", "0.81", "ACCOUNT_TAKEOVER", "4"],
      ["Juan Manuel Salgueiro", "0.89", "ROUND_TRIPPING", "6"]
    ];
  } else if (normalized.includes("mule") || normalized.includes("mulero")) {
    columns = ["MuleAccount", "Bank", "BalanceReceivedARS", "IdentifiedIP"];
    rows = [
      ["CBU Galicia 007001", "Banco Galicia", "1,500,000", "181.22.9.11"],
      ["CBU Galicia 007002", "Banco Galicia", "1,350,000", "181.22.9.12"]
    ];
  } else {
    rows = [
      ["Eduardo S. Rodríguez", "0.94", "SMURFING", "5"],
      ["Sofía Martínez de Hoz", "0.81", "ACCOUNT_TAKEOVER", "4"],
      ["Gabriela Bianchi", "0.72", "LAYERING", "3"]
    ];
  }

  res.json({
    columns,
    rows,
    queryExecuted: query,
    timestamp: new Date().toISOString()
  });
});

// START EXPRESS/VITE ENGINE
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Nexus Sentinel Swarm server is running at http://0.0.0.0:${PORT}`);
  });
}

startServer();
