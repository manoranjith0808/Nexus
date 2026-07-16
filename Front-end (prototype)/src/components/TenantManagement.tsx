import React, { useState, useEffect } from "react";
import { Tenant } from "../types.js";
import { Landmark, Plus, Edit2, Trash2, Check, X, ShieldAlert, Globe, HelpCircle } from "lucide-react";
import { motion } from "motion/react";

export default function TenantManagement() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [isEditing, setIsEditing] = useState<string | null>(null); // Tenant ID being edited
  const [isAdding, setIsAdding] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Form states
  const [name, setName] = useState("");
  const [country, setCountry] = useState("UY");
  const [regulatoryFramework, setRegulatoryFramework] = useState("");
  const [riskThreshold, setRiskThreshold] = useState(0.65);

  const fetchTenants = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/tenants");
      if (res.ok) {
        setTenants(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch tenants:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      const res = await fetch("/api/tenants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, country, regulatoryFramework, riskThreshold })
      });

      if (res.ok) {
        setIsAdding(false);
        resetForm();
        fetchTenants();
      }
    } catch (err) {
      console.error("Failed to create tenant:", err);
    }
  };

  const handleUpdate = async (id: string) => {
    try {
      const res = await fetch(`/api/tenants/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, country, regulatoryFramework, riskThreshold })
      });

      if (res.ok) {
        setIsEditing(null);
        resetForm();
        fetchTenants();
      }
    } catch (err) {
      console.error("Failed to update tenant:", err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this tenant bank from the Swarm?")) return;

    try {
      const res = await fetch(`/api/tenants/${id}`, {
        method: "DELETE"
      });

      if (res.ok) {
        fetchTenants();
      }
    } catch (err) {
      console.error("Failed to delete tenant:", err);
    }
  };

  const startEdit = (t: Tenant) => {
    setIsEditing(t.id);
    setName(t.name);
    setCountry(t.country);
    setRegulatoryFramework(t.regulatoryFramework);
    setRiskThreshold(t.riskThreshold);
  };

  const resetForm = () => {
    setName("");
    setCountry("UY");
    setRegulatoryFramework("");
    setRiskThreshold(0.65);
  };

  return (
    <div className="space-y-6">
      {/* Header Panel */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-zinc-900/40 p-4.5 rounded-xl border border-zinc-850">
        <div>
          <h2 className="text-sm font-mono font-bold text-zinc-200 uppercase tracking-wider">TENANT AND BANK ENTITY MANAGEMENT</h2>
          <p className="text-xs text-zinc-400 mt-0.5">Define compliance regulatory frameworks and risk thresholds per country.</p>
        </div>
        {!isAdding && (
          <button
            onClick={() => { setIsAdding(true); resetForm(); }}
            className="flex items-center gap-1.5 text-xs font-mono font-bold bg-emerald-500 hover:bg-emerald-600 text-zinc-950 px-3 py-2 rounded-lg transition shrink-0 cursor-pointer"
          >
            <Plus className="w-4 h-4" /> Register Bank (UY/AR)
          </button>
        )}
      </div>

      {/* Adding Panel Form */}
      {isAdding && (
        <motion.form
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={handleCreate}
          className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 space-y-4"
        >
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <h3 className="text-xs font-mono font-bold text-zinc-200 uppercase flex items-center gap-2">
              <Plus className="w-4 h-4 text-emerald-400" /> Register New Bank / Regulated Entity
            </h3>
            <button
              type="button"
              onClick={() => setIsAdding(false)}
              className="text-zinc-500 hover:text-zinc-300 text-xs font-mono cursor-pointer"
            >
              Cancel
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Field 1: Name */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Commercial Bank Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Itaú Bank Uruguay S.A."
                className="w-full bg-zinc-950 border border-zinc-800 hover:border-zinc-700 focus:border-emerald-500/50 rounded-lg p-2.5 text-xs text-zinc-200 focus:outline-none"
              />
            </div>

            {/* Field 2: Country */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Country Jurisdiction</label>
              <div className="flex gap-3">
                {["UY", "AR"].map((co) => (
                  <button
                    key={co}
                    type="button"
                    onClick={() => setCountry(co)}
                    className={`flex-1 p-2.5 rounded-lg border text-xs font-mono font-bold transition ${
                      country === co
                        ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400"
                        : "bg-zinc-950 border-zinc-800 hover:border-zinc-750 text-zinc-400"
                    }`}
                  >
                    {co === "UY" ? "URUGUAY (BCU)" : "ARGENTINA (UIF / BCRA)"}
                  </button>
                ))}
              </div>
            </div>

            {/* Field 3: Regulatory Framework */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Compliance Regulatory Framework</label>
              <input
                type="text"
                required
                value={regulatoryFramework}
                onChange={(e) => setRegulatoryFramework(e.target.value)}
                placeholder="e.g. BCU Circular 315/2022 or Law 19,574"
                className="w-full bg-zinc-950 border border-zinc-800 hover:border-zinc-700 focus:border-emerald-500/50 rounded-lg p-2.5 text-xs text-zinc-200 focus:outline-none"
              />
            </div>

            {/* Field 4: Risk Threshold */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[10px] font-mono font-bold text-zinc-400 uppercase">Risk Tolerance Threshold</label>
                <span className="text-[10px] font-mono font-bold text-emerald-400">{(riskThreshold * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.30"
                max="0.90"
                step="0.05"
                value={riskThreshold}
                onChange={(e) => setRiskThreshold(parseFloat(e.target.value))}
                className="w-full accent-emerald-400 cursor-pointer h-1.5 bg-zinc-800 rounded-lg appearance-none"
              />
              <p className="text-[9px] text-zinc-500 font-mono">
                * Alerts with a risk score exceeding this threshold will automatically be flagged as critical.
              </p>
            </div>
          </div>

          <div className="flex justify-end gap-2.5 border-t border-zinc-800 pt-3">
            <button
              type="submit"
              className="px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-zinc-950 text-xs font-mono font-bold rounded-lg transition cursor-pointer"
            >
              Register Entity
            </button>
          </div>
        </motion.form>
      )}

      {/* Tenants Grid list */}
      {isLoading ? (
        <div className="text-center p-8 font-mono text-xs text-zinc-500">Loading tenants...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {tenants.map((t) => {
            const isEditingThis = isEditing === t.id;
            return (
              <div
                key={t.id}
                className="bg-zinc-900/30 border border-zinc-800 rounded-xl p-5 flex flex-col justify-between relative overflow-hidden group hover:border-zinc-700 transition"
              >
                {/* Decorative node highlight */}
                <div className="absolute right-0 top-0 w-20 h-20 bg-emerald-500/1 rounded-full blur-xl pointer-events-none" />

                {isEditingThis ? (
                  <div className="space-y-4 w-full">
                    <div className="text-xs font-mono font-bold text-emerald-400 border-b border-zinc-800 pb-2 flex items-center gap-2">
                      <Edit2 className="w-4 h-4" /> EDITING TENANT
                    </div>

                    <div className="space-y-2 text-xs font-mono">
                      <div>
                        <label className="text-[9px] text-zinc-500 block mb-1">Name</label>
                        <input
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded p-1.5 text-xs text-zinc-200 focus:outline-none"
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[9px] text-zinc-500 block mb-1">Country</label>
                          <select
                            value={country}
                            onChange={(e) => setCountry(e.target.value)}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded p-1.5 text-xs text-zinc-200 focus:outline-none"
                          >
                            <option value="UY">UY</option>
                            <option value="AR">AR</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-[9px] text-zinc-500 block mb-1">Threshold</label>
                          <input
                            type="number"
                            step="0.05"
                            value={riskThreshold}
                            onChange={(e) => setRiskThreshold(parseFloat(e.target.value))}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded p-1.5 text-xs text-zinc-200 focus:outline-none"
                          />
                        </div>
                      </div>
                      <div>
                        <label className="text-[9px] text-zinc-500 block mb-1">Regulatory Framework</label>
                        <input
                          type="text"
                          value={regulatoryFramework}
                          onChange={(e) => setRegulatoryFramework(e.target.value)}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded p-1.5 text-xs text-zinc-200 focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
                      <button
                        onClick={() => setIsEditing(null)}
                        className="px-2.5 py-1.5 rounded bg-zinc-850 hover:bg-zinc-800 text-zinc-400 text-xs font-mono transition cursor-pointer"
                      >
                        <X className="w-3.5 h-3.5 inline-block mr-1" /> Cancel
                      </button>
                      <button
                        onClick={() => handleUpdate(t.id)}
                        className="px-2.5 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 text-zinc-950 text-xs font-mono font-bold transition cursor-pointer"
                      >
                        <Check className="w-3.5 h-3.5 inline-block mr-1" /> Save
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col justify-between space-y-4">
                    {/* Upper content */}
                    <div>
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2.5 bg-zinc-950 rounded-lg border border-zinc-850 text-zinc-400 group-hover:text-emerald-400 transition">
                            <Landmark className="w-5 h-5" />
                          </div>
                          <div>
                            <h4 className="text-xs font-mono font-bold text-zinc-200">{t.name}</h4>
                            <p className="text-[10px] font-mono text-zinc-500">{t.id}</p>
                          </div>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-zinc-950 text-zinc-400 border border-zinc-800 uppercase font-mono text-[9px]">
                          {t.country}
                        </span>
                      </div>

                      <div className="mt-4 space-y-2 text-[11px] font-mono text-zinc-400">
                        <div className="flex justify-between border-b border-zinc-850 pb-1.5">
                          <span className="text-zinc-500">Regulation:</span>
                          <span className="text-zinc-300 font-medium truncate max-w-[200px]" title={t.regulatoryFramework}>
                            {t.regulatoryFramework}
                          </span>
                        </div>
                        <div className="flex justify-between border-b border-zinc-850 pb-1.5">
                          <span className="text-zinc-500">Alert Threshold:</span>
                          <span className="text-emerald-400 font-bold">{(t.riskThreshold * 100)}%</span>
                        </div>
                        <div className="flex justify-between pb-1">
                          <span className="text-zinc-500">Created At:</span>
                          <span className="text-zinc-400">{new Date(t.createdAt).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>

                    {/* Bottom buttons panel */}
                    <div className="flex items-center justify-end gap-1.5 pt-3 border-t border-zinc-800/40 mt-2">
                      <button
                        onClick={() => startEdit(t)}
                        className="p-1.5 rounded bg-zinc-950 hover:bg-zinc-800 border border-zinc-850 hover:border-zinc-700 text-zinc-400 hover:text-zinc-200 transition cursor-pointer"
                        title="Edit Settings"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(t.id)}
                        className="p-1.5 rounded bg-rose-500/5 hover:bg-rose-500/10 border border-rose-500/10 hover:border-rose-500/30 text-rose-400 transition cursor-pointer"
                        title="Delete Entity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
