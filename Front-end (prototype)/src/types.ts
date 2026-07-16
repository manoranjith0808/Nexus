export enum Verdict {
  DISCARD = "DISCARD",
  MONITOR = "MONITOR",
  ESCALATE = "ESCALATE",
  BLOCK = "BLOCK"
}

export enum CaseStatus {
  OPEN = "OPEN",
  INVESTIGATING = "INVESTIGATING",
  DECIDED = "DECIDED",
  EXECUTED = "EXECUTED",
  CLOSED = "CLOSED"
}

export enum PatternType {
  SMURFING = "SMURFING",
  ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER",
  SYNTHETIC_IDENTITY = "SYNTHETIC_IDENTITY",
  LAYERING = "LAYERING",
  INSURANCE_FRAUD = "INSURANCE_FRAUD",
  CARD_CAROUSEL = "CARD_CAROUSEL",
  ROUND_TRIPPING = "ROUND_TRIPPING"
}

export interface Tenant {
  id: string;
  name: string;
  country: string; // "UY" | "AR"
  regulatoryFramework: string;
  riskThreshold: number; // 0 to 1
  createdAt: string;
}

export interface Alert {
  id: string; // Case ID or Alert ID
  caseId: string;
  customerName: string;
  customerDocument: string; // C.I., CUIT, etc.
  riskScore: number; // 0 to 1
  confidenceScore: number; // 0 to 1
  verdict: Verdict;
  status: CaseStatus;
  country: string; // "UY" | "AR"
  tenantId: string;
  tenantName: string;
  pattern: PatternType;
  amount: number;
  currency: string; // "USD" | "UYU" | "ARS"
  timestamp: string;
  assignedTo: string | null; // analyst email/name
}

export interface AgentReport {
  agentId: string; // 1 to 6
  agentName: string;
  caseId: string;
  timestamp: string;
  riskScore: number; // 0-1
  confidence: number; // 0-1
  findings: string[];
  flags?: string[];
  evidence?: Record<string, any>;
  recommendation: string;
  latencyMs: number;
  isSimulated: boolean;
}

export interface AuditLogEntry {
  id: string;
  caseId: string;
  timestamp: string;
  user: string;
  role: string;
  action: string;
  details: string;
}

export interface NetworkNode {
  id: string;
  label: string;
  type: "account" | "device" | "ip" | "merchant" | "atm";
  val: number; // node size/weight
  color?: string;
  riskScore?: number;
}

export interface NetworkLink {
  source: string;
  target: string;
  label: string;
  amount?: number;
  weight?: number;
}

export interface NetworkGraph {
  nodes: NetworkNode[];
  links: NetworkLink[];
}

export interface CaseDetails {
  id: string;
  alert: Alert;
  narrative: string;
  aiReasoning: string[]; // step by step explanation
  timeline: {
    event: string;
    timestamp: string;
    latencyMs: number;
    icon?: string;
  }[];
  auditLogs: AuditLogEntry[];
  graph: NetworkGraph;
  rosReport: {
    subjectName: string;
    documentType: string;
    documentNumber: string;
    reportDate: string;
    suspiciousActivities: string;
    recommendedActions: string;
    regulatoryCode: string;
    narrativeSummary: string;
  };
}
