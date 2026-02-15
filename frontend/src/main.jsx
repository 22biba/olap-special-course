import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

const API_BASE = "http://localhost:8000";

function App() {
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [conversationHistory, setConversationHistory] = useState([]);

  async function runWithPayload(payload) {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const reqBody = { ...payload, conversation_history: conversationHistory };
      const resp = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reqBody),
      });
      if (!resp.ok) throw new Error(await resp.text() || `HTTP ${resp.status}`);
      const data = await resp.json();
      const res = data.result;
      setResult(res);
      setConversationHistory((prev) => [
        ...prev,
        { query: payload.natural_language_query, result: res },
      ]);
    } catch (err) {
      setError(err.message || "Failed to run query");
    } finally {
      setLoading(false);
    }
  }

  async function runChatQuery(e) {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const q = chatInput.trim();
    await runWithPayload({ natural_language_query: q });
    setChatInput("");
  }

  function onFollowUp(suggestion) {
    setChatInput(suggestion);
    runWithPayload({ natural_language_query: suggestion });
  }

  const report = result?.report;
  const table = report?.table ?? [];
  const columns = table.length > 0 ? Object.keys(table[0]) : [];
  const bestPerformer = result?.best_performer;
  const drill = result?.drill;
  const totals = report?.totals ?? {};
  const formattingRules = report?.formatting?.rules ?? [];
  const cubeResult = result?.cube_result || result?.cube || result?.pivot;
  const kpiResult = result?.kpi_result;
  const cubeData = cubeResult?.data ?? cubeResult?.table ?? [];
  const cubeCols = cubeData.length > 0 ? Object.keys(cubeData[0]) : [];

  function cellStyle(col, value) {
    for (const rule of formattingRules) {
      if (rule.columns && rule.columns.includes(col)) {
        const n = Number(value);
        if (!Number.isNaN(n)) {
          if (n > 0) return { color: rule.positive === "green" ? "#059669" : undefined };
          if (n < 0) return { color: rule.negative === "red" ? "#dc2626" : undefined };
        }
      }
    }
    return {};
  }

  function renderTable(data, colList, applyFormatting = false) {
    if (!data.length) return <p>No rows.</p>;
    const cols = colList.length ? colList : Object.keys(data[0]);
    return (
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", minWidth: 400 }}>
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c} style={{ borderBottom: "1px solid #e5e7eb", textAlign: "left", padding: "0.4rem 0.6rem", background: "#f9fafb" }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, idx) => (
              <tr key={idx}>
                {cols.map((c) => (
                  <td key={c} style={{ borderBottom: "1px solid #f3f4f6", padding: "0.4rem 0.6rem", ...(applyFormatting ? cellStyle(c, row[c]) : {}) }}>
                    {typeof row[c] === "number" ? row[c].toFixed(4) : String(row[c] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const nameKey = columns.find((c) => ["region", "category", "segment", "country"].includes(c)) || columns[0];
  const chartData = table
    .filter((r) => r[nameKey] != null)
    .map((r) => ({
      name: String(r[nameKey] ?? "—"),
      revenue: Number(r.revenue_current ?? r.revenue ?? 0),
      growth: Number(r.revenue_growth ?? 0),
    }))
    .slice(0, 10);

  const followUpSuggestions = report?.follow_up_suggestions ?? [];

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "1.5rem", maxWidth: 960 }}>
      <h1 style={{ marginBottom: "0.5rem" }}>OLAP BI Platform</h1>
      <p style={{ marginBottom: "1rem", color: "#444" }}>
        Ask questions in natural language. Multi-agent BI: Slice, Dice, Drill-down, Roll-up, Pivot, KPIs, Reports.
      </p>

      <form onSubmit={runChatQuery} style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="e.g. Compare Q3 vs Q4 2024 by region"
            style={{ flex: 1, padding: "0.5rem 0.75rem", borderRadius: 6, border: "1px solid #d1d5db" }}
          />
          <button type="submit" disabled={loading} style={{ padding: "0.5rem 1rem", fontWeight: 600, borderRadius: 6, border: "none", background: "#2563eb", color: "white", cursor: "pointer" }}>
            {loading ? "Analyzing…" : "Ask"}
          </button>
        </div>
      </form>

      {error && <div style={{ marginBottom: "1rem", padding: "0.75rem", borderRadius: 4, background: "#fee2e2", color: "#991b1b" }}>{error}</div>}

      {result && (
        <>
          {followUpSuggestions.length > 0 && (
            <div style={{ marginBottom: "1rem" }}>
              <span style={{ fontSize: "0.9rem", color: "#6b7280" }}>Follow-up: </span>
              {followUpSuggestions.map((s) => (
              <button key={s} type="button" onClick={() => onFollowUp(s)} style={{ marginRight: "0.5rem", marginTop: "0.25rem", padding: "0.25rem 0.5rem", fontSize: "0.8rem", borderRadius: 4, border: "1px solid #e5e7eb", background: "#f9fafb", cursor: "pointer" }}>
                {s}
              </button>
              ))}
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* 1. Cube Operations Agent */}
          {cubeResult && (
            <section style={{ padding: "1rem", background: "#fef3c7", borderRadius: 8, border: "1px solid #fcd34d" }}>
              <h2 style={{ marginBottom: "0.25rem", fontSize: "1.1rem" }}>Cube Operations Agent</h2>
              <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.85rem", color: "#92400e" }}>
                Slice: single dimension · Dice: multiple dimensions · Pivot: reorganize perspective
              </p>
              <p style={{ margin: "0 0 0.5rem 0", fontWeight: 600 }}>Operation: {cubeResult.operation || cubeResult.type || "dice"}</p>
              {renderTable(cubeData, cubeCols, false)}
            </section>
          )}

          {/* 2. KPI Calculator Agent */}
          {(kpiResult || result?.kpi_data) && (
            <section style={{ padding: "1rem", background: "#ede9fe", borderRadius: 8, border: "1px solid #c4b5fd" }}>
              <h2 style={{ marginBottom: "0.25rem", fontSize: "1.1rem" }}>KPI Calculator Agent</h2>
              <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.85rem", color: "#5b21b6" }}>
                Year-over-year (YoY) growth · Month-over-month (MoM) · Profit margins · Rankings (Top N)
              </p>
              <p style={{ margin: "0 0 0.5rem 0", fontWeight: 600 }}>Applied: {kpiResult?.kpi_type || "yoy_growth"}</p>
              {bestPerformer && (
                <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem" }}>
                  Best performer: <strong>{bestPerformer.region ?? Object.values(bestPerformer)[0]}</strong>
                </p>
              )}
              {renderTable(table.length ? table : (result?.kpi_data ?? []), columns, true)}
            </section>
          )}

          {/* Chart */}
          {chartData.length > 0 && (
            <section style={{ padding: "1rem", background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
              <h2 style={{ marginBottom: "0.5rem", fontSize: "1rem" }}>Chart – Revenue by region</h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => Number(v).toFixed(2)} />
                  <Legend />
                  <Bar dataKey="revenue" name="Revenue" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="growth" name="Growth" fill="#059669" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* Dimension Navigator */}
          {drill && (
            <section style={{ padding: "1rem", background: "#eff6ff", borderRadius: 8, border: "1px solid #bfdbfe" }}>
              <h2 style={{ marginBottom: "0.5rem", fontSize: "1rem" }}>Dimension Navigator (drill-down)</h2>
              <p style={{ margin: "0 0 0.5rem 0" }}>
                Current level: <strong>{drill.current_level}</strong> → Next level: <strong>{drill.next_level}</strong>
              </p>
              {drill.members?.length > 0 && (
                <p style={{ margin: 0, fontSize: "0.9rem" }}>Members: {drill.members.map((m) => m.value).join(", ")}</p>
              )}
            </section>
          )}

          {/* 3. Report Generator Agent */}
          {report && (
            <section style={{ padding: "1rem", background: "#d1fae5", borderRadius: 8, border: "1px solid #6ee7b7" }}>
              <h2 style={{ marginBottom: "0.25rem", fontSize: "1.1rem" }}>Report Generator Agent</h2>
              <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.85rem", color: "#065f46" }}>
                Formatted tables with totals · Conditional formatting hints · Executive summaries
              </p>
              <h3 style={{ marginBottom: "0.25rem", fontSize: "0.95rem" }}>Executive summary</h3>
              <p style={{ marginBottom: "1rem" }}>{report.summary}</p>
              {Object.keys(totals).length > 0 && (
                <>
                  <h3 style={{ marginBottom: "0.25rem", fontSize: "0.95rem" }}>Totals</h3>
                  <p style={{ marginBottom: "1rem" }}>
                    {Object.entries(totals).map(([k, v]) => (
                      <span key={k} style={{ marginRight: "1rem" }}><strong>{k}:</strong> {typeof v === "number" ? v.toFixed(4) : String(v)}</span>
                    ))}
                  </p>
                </>
              )}
              {formattingRules.length > 0 && (
                <p style={{ marginBottom: "0.75rem", fontSize: "0.85rem", color: "#047857" }}>
                  Formatting: positive = green, negative = red for growth/margin columns
                </p>
              )}
              <h3 style={{ marginBottom: "0.5rem", fontSize: "0.95rem" }}>Formatted table</h3>
              {table.length === 0 ? <p>No rows.</p> : renderTable(table, columns, true)}
            </section>
          )}
          </div>
        </>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
