import React, { useState, useEffect } from "react";
import { PatternType, Tenant } from "../types.js";
import { PlusCircle, UploadCloud, RefreshCw, FileText, Play, CheckCircle, HelpCircle, ArrowRight } from "lucide-react";
import { motion } from "motion/react";

interface EventSubmissionTestingProps {
  onCaseCreated?: (caseId: string) => void;
}

export default function EventSubmissionTesting({ onCaseCreated }: EventSubmissionTestingProps) {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isBulkSubmitting, setIsBulkSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<"manual" | "bulk">("manual");

  // Form fields
  const [customerName, setCustomerName] = useState("");
  const [customerDocument, setCustomerDocument] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [pattern, setPattern] = useState(PatternType.SMURFING);
  const [remarks, setRemarks] = useState("");

  // Bulk uploading states
  const [bulkJson, setBulkJson] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    async function loadTenants() {
      try {
        const res = await fetch("/api/tenants");
        if (res.ok) {
          const list = await res.json();
          setTenants(list);
          if (list.length > 0) setSelectedTenantId(list[0].id);
        }
      } catch (err) {
        console.error("Failed to load tenants:", err);
      }
    }
    loadTenants();
  }, []);

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customerName || !customerDocument || !amount) return;

    setIsSubmitting(true);
    setFeedback(null);
    try {
      const res = await fetch("/api/events/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customerName,
          customerDocument,
          tenantId: selectedTenantId,
          amount,
          currency,
          pattern,
          remarks
        })
      });

      if (res.ok) {
        const data = await res.json();
        setFeedback(`Alert successfully generated. Created Case ID: ${data.caseId}`);
        // Reset manual form
        setCustomerName("");
        setCustomerDocument("");
        setAmount("");
        setRemarks("");
        if (onCaseCreated) onCaseCreated(data.caseId);
      } else {
        setFeedback("Error processing simulation event.");
      }
    } catch (err) {
      console.error(err);
      setFeedback("Server connection error.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const loadExampleBulkJson = () => {
    const example = {
      events: [
        {
          customerName: "Carlos Salvador Bilardo",
          customerDocument: "AR-CUIT 20-11294021-3",
          tenantId: selectedTenantId || "tenant-bnaAR",
          amount: 1450000,
          currency: "ARS",
          pattern: "SMURFING"
        },
        {
          customerName: "Yamandú Orsi Pereira",
          customerDocument: "UY-CI 3.190.220-4",
          tenantId: selectedTenantId || "tenant-broU",
          amount: 12000,
          currency: "USD",
          pattern: "ACCOUNT_TAKEOVER"
        }
      ]
    };
    setBulkJson(JSON.stringify(example, null, 2));
  };

  const handleBulkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkJson.trim()) return;

    setIsBulkSubmitting(true);
    setFeedback(null);
    try {
      const parsed = JSON.parse(bulkJson);
      const res = await fetch("/api/events/process/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed)
      });

      if (res.ok) {
        const data = await res.json();
        setFeedback(`Bulk ingestion completed. Successfully created ${data.processedCount} alerts.`);
        setBulkJson("");
        if (onCaseCreated && data.processedIds?.length > 0) {
          onCaseCreated(data.processedIds[0]); // focus on the first created case
        }
      } else {
        setFeedback("Error processing bulk ingestion JSON.");
      }
    } catch (err) {
      console.error(err);
      setFeedback("Error: Please verify the JSON syntax format.");
    } finally {
      setIsBulkSubmitting(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Sidebar explanation panel */}
      <div className="space-y-4">
        <div className="bg-zinc-900/40 p-5 rounded-xl border border-zinc-850 h-full flex flex-col justify-between">
          <div className="space-y-4">
            <div>
              <span className="text-[10px] font-mono font-bold text-emerald-400 uppercase tracking-wider block mb-1">Simulation Environment</span>
              <h2 className="text-sm font-mono font-bold text-zinc-100 uppercase">Event Ingestion Hub</h2>
            </div>
            
            <p className="text-xs text-zinc-400 font-mono leading-relaxed">
              Trigger simulated fraud scenarios deterministically or dynamically using intelligent <span className="text-zinc-200 font-bold">AI Generation (Gemini V2.5)</span>.
            </p>

            <div className="space-y-3 pt-2 text-[11px] font-mono text-zinc-400">
              <div className="p-3 bg-zinc-950/60 rounded border border-zinc-850">
                <span className="font-bold text-zinc-200 block mb-1">Heuristic Fallback Mode:</span>
                <span>If no API Key is configured, the Swarm evaluates telemetry data using deterministic local fallback templates.</span>
              </div>
              <div className="p-3 bg-zinc-950/60 rounded border border-zinc-850">
                <span className="font-bold text-zinc-200 block mb-1">AI Swarm Reasoning (Gemini):</span>
                <span>Upon event submission, Gemini will automatically draft a detailed transaction narrative, orchestrate multi-agent analysis steps, and structure regulatory SAR models.</span>
              </div>
            </div>
          </div>

          <div className="text-[9px] font-mono text-zinc-500 border-t border-zinc-850 pt-4 mt-4">
            Compliance Testbed Console · Nexus Sentinel Swarm
          </div>
        </div>
      </div>

      {/* Main Testing/Submission Panel */}
      <div className="lg:col-span-2 bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 flex flex-col">
        {/* Tab triggers */}
        <div className="flex border-b border-zinc-800 mb-5 text-xs font-mono">
          <button
            onClick={() => { setActiveTab("manual"); setFeedback(null); }}
            className={`pb-2.5 px-4 font-bold border-b-2 transition cursor-pointer ${
              activeTab === "manual" ? "border-emerald-500 text-emerald-400" : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            MANUAL ALERT INGESTION
          </button>
          <button
            onClick={() => { setActiveTab("bulk"); setFeedback(null); }}
            className={`pb-2.5 px-4 font-bold border-b-2 transition cursor-pointer ${
              activeTab === "bulk" ? "border-emerald-500 text-emerald-400" : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            BULK INGESTION (JSON)
          </button>
        </div>

        {/* Feedback message display */}
        {feedback && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4 p-3 rounded-lg border bg-zinc-950 text-xs font-mono flex items-center gap-2.5"
          >
            <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0" />
            <span className="text-zinc-200 font-medium">{feedback}</span>
          </motion.div>
        )}

        {/* Manual Tab content */}
        {activeTab === "manual" ? (
          <form onSubmit={handleManualSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Full Customer Name</label>
                <input
                  type="text"
                  required
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="e.g. Eduardo Rodríguez"
                  className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">National ID / CUIT Number</label>
                <input
                  type="text"
                  required
                  value={customerDocument}
                  onChange={(e) => setCustomerDocument(e.target.value)}
                  placeholder="e.g. UY-CI 4.819.301-2"
                  className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Transaction Amount</label>
                <input
                  type="number"
                  required
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="e.g. 14500"
                  className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Currency</label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none"
                >
                  <option value="USD">USD (US Dollars)</option>
                  <option value="UYU">UYU (Uruguayan Pesos)</option>
                  <option value="ARS">ARS (Argentine Pesos)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Typological Pattern</label>
                <select
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value as PatternType)}
                  className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none cursor-pointer"
                >
                  <option value={PatternType.SMURFING}>SMURFING (Structuring)</option>
                  <option value={PatternType.ACCOUNT_TAKEOVER}>ACCOUNT TAKEOVER (ATO)</option>
                  <option value={PatternType.SYNTHETIC_IDENTITY}>SYNTHETIC IDENTITY</option>
                  <option value={PatternType.LAYERING}>LAYERING (Layering Scheme)</option>
                  <option value={PatternType.INSURANCE_FRAUD}>INSURANCE FRAUD</option>
                  <option value={PatternType.CARD_CAROUSEL}>CARD CAROUSEL</option>
                  <option value={PatternType.ROUND_TRIPPING}>ROUND TRIPPING</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Originating Bank / Tenant</label>
                <select
                  value={selectedTenantId}
                  onChange={(e) => setSelectedTenantId(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none cursor-pointer"
                >
                  {tenants.map(t => (
                    <option key={t.id} value={t.id}>{t.name} ({t.country})</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Event Comments & Observations (Optional)</label>
              <textarea
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Describe any unusual indicators observed..."
                rows={3}
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-2.5 text-xs font-mono text-zinc-200 focus:outline-none"
              />
            </div>

            <div className="border-t border-zinc-800 pt-4 flex justify-end">
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-zinc-800 text-zinc-950 disabled:text-zinc-500 px-4 py-2 rounded-lg font-mono font-bold text-xs transition cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Processing and instantiating case...
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" /> Trigger Event in Swarm
                  </>
                )}
              </button>
            </div>
          </form>
        ) : (
          /* Bulk JSON Tab Content */
          <form onSubmit={handleBulkSubmit} className="space-y-4 flex-1 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Bulk File Upload (JSON)</label>
                <button
                  type="button"
                  onClick={loadExampleBulkJson}
                  className="text-[10px] text-emerald-400 hover:text-emerald-300 font-mono font-bold border border-emerald-500/20 px-2 py-0.5 rounded bg-emerald-500/5 transition cursor-pointer"
                >
                  Load Example Template
                </button>
              </div>
              <textarea
                value={bulkJson}
                onChange={(e) => setBulkJson(e.target.value)}
                rows={8}
                placeholder="Paste bulk JSON payload here..."
                className="w-full bg-zinc-950 border border-zinc-800 focus:border-emerald-500/40 rounded-lg p-3 font-mono text-[11px] text-zinc-200 focus:outline-none"
              />
            </div>

            <div className="border-t border-zinc-800 pt-4 flex justify-end">
              <button
                type="submit"
                disabled={isBulkSubmitting || !bulkJson.trim()}
                className="flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-zinc-800 text-zinc-950 disabled:text-zinc-500 px-4 py-2 rounded-lg font-mono font-bold text-xs transition cursor-pointer"
              >
                {isBulkSubmitting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Importing batch...
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-4 h-4" /> Execute Bulk Ingestion
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
