import React, { useState, useRef, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

const API_BASE = "http://localhost:8000";

function App() {
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conversationHistory, setConversationHistory] = useState([]);
  const [pendingQuery, setPendingQuery] = useState(null);
  const chatEndRef = useRef(null);

  function clearChat() {
    setConversationHistory([]);
    setPendingQuery(null);
    setError("");
    setChatInput("");
  }

  async function runWithPayload(payload) {
    setLoading(true);
    setError("");
    setPendingQuery(payload.natural_language_query || null);
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
      setConversationHistory((prev) => [
        ...prev,
        { query: payload.natural_language_query, result: res },
      ]);
    } catch (err) {
      setError(err.message || "Failed to run query");
    } finally {
      setLoading(false);
      setPendingQuery(null);
    }
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversationHistory, pendingQuery]);

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

  function cellStyle(col, value, formattingRules = []) {
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

  function renderTable(data, colList, applyFormatting = false, formattingRules = []) {
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
                  <td key={c} style={{ borderBottom: "1px solid #f3f4f6", padding: "0.4rem 0.6rem", ...(applyFormatting ? cellStyle(c, row[c], formattingRules) : {}) }}>
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

  function renderExchange(item, index, isLatest) {
    const res = item.result;
    const query = item.query || "";
    const report = res?.report;
    const table = report?.table ?? [];
    const columns = table.length > 0 ? Object.keys(table[0]) : [];
    const bestPerformer = res?.best_performer;
    const drill = res?.drill;
    const totals = report?.totals ?? {};
    const formattingRules = report?.formatting?.rules ?? [];
    const cubeResult = res?.cube_result || res?.cube || res?.pivot;
    const kpiResult = res?.kpi_result;
    const cubeData = cubeResult?.data ?? cubeResult?.table ?? [];
    const cubeCols = cubeData.length > 0 ? Object.keys(cubeData[0]) : [];
    const followUpSuggestions = report?.follow_up_suggestions ?? [];
    const isCompound = res?.compound === true;
    const step0Result = res?.step0?.result;
    const step0CubeData = step0Result?.cube_result?.data ?? step0Result?.cube?.data ?? [];
    const step0CubeCols = step0CubeData.length > 0 ? Object.keys(step0CubeData[0]) : [];

    const chartDimensionKey = columns.find((c) => ["date_quarter", "date_year", "region", "country", "category", "segment"].includes(c)) || columns[0];
    const nameKey = chartDimensionKey;
    const hasProfit = columns.some((c) => c === "profit_current" || c === "profit_growth" || c === "profit_margin");
    const valueKey = hasProfit ? "profit_current" : "revenue_current";
    const growthKey = hasProfit ? "profit_growth" : "revenue_growth";
    const fallbackValueKey = hasProfit ? "profit" : "revenue";
    const chartData = table
      .filter((r) => r[nameKey] != null)
      .map((r) => ({
        name: String(r[nameKey] ?? "—"),
        value: Number(r[valueKey] ?? r[fallbackValueKey] ?? 0),
        growth: Number(r[growthKey] ?? 0),
      }))
      .slice(0, 10);
    const measureLabel = hasProfit ? "Profit" : "Revenue";
    const chartTitleByDimension = {
      date_quarter: `${measureLabel} by quarter`,
      date_year: `${measureLabel} by year`,
      region: `${measureLabel} by region`,
      country: `${measureLabel} by country`,
      category: `${measureLabel} by category`,
      segment: `${measureLabel} by segment`,
    };
    const chartTitle = chartTitleByDimension[chartDimensionKey] || `${measureLabel} by ${chartDimensionKey}`;

    return (
      <React.Fragment key={index}>
        {/* User message bubble */}
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <div style={{ maxWidth: "75%", background: "#2563eb", color: "white", padding: "0.75rem 1rem", borderRadius: "18px 18px 4px 18px", fontSize: "0.95rem", boxShadow: "0 4px 10px rgba(37, 99, 235, 0.3)" }}>
            {query}
          </div>
        </div>
        {/* Follow-up suggestions - only for latest */}
        {isLatest && followUpSuggestions.length > 0 && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{ maxWidth: "80%", background: "#f1f5f9", padding: "0.75rem 1rem", borderRadius: "18px 18px 18px 4px", fontSize: "0.85rem" }}>
              <div style={{ marginBottom: "0.4rem", color: "#0f172a", fontWeight: 600 }}>Follow-up ideas</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                {followUpSuggestions.map((s) => (
                  <button key={s} type="button" onClick={() => onFollowUp(s)} style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem", borderRadius: 999, border: "1px solid #e5e7eb", background: "white", cursor: "pointer" }}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
        {/* Assistant response with agents + visuals */}
        <div style={{ display: "flex", justifyContent: "flex-start" }}>
          <div style={{ flex: 1, maxWidth: "100%", background: "#f8fafc", borderRadius: "18px 18px 18px 4px", padding: "1rem", border: "1px solid #e2e8f0", boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)" }}>
            <div style={{ marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <div style={{ width: 28, height: 28, borderRadius: "999px", background: "linear-gradient(135deg, #4f46e5, #22c55e)", display: "flex", alignItems: "center", justifyContent: "center", color: "white", fontSize: "0.8rem", fontWeight: 700 }}>BI</div>
              <div style={{ fontSize: "0.85rem", color: "#0f172a" }}>
                {isCompound ? `Part 1 & 2: ${res?.step0?.query ?? "Part 1"}, then ${res?.step1?.query ?? "Part 2"}.` : "Multi-agent analysis: cube, KPIs, drill-down and report."}
              </div>
            </div>
            {isCompound && step0CubeData.length > 0 && (
              <section style={{ marginBottom: "1rem", padding: "0.75rem 0.85rem", background: "#eff6ff", borderRadius: 10, border: "1px solid #bfdbfe" }}>
                <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.95rem" }}>Part 1: {res?.step0?.query ?? "Revenue by year"}</h3>
                <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.8rem", color: "#1e40af" }}>{step0CubeCols.includes("date_year") ? "Revenue breakdown by year (2022, 2023, 2024)." : "Totals by category."}</p>
                {renderTable(step0CubeData, step0CubeCols, false, formattingRules)}
              </section>
            )}
            {isCompound && step0CubeData.length > 0 && <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.95rem", color: "#0f172a" }}>Part 2: {res?.step1?.query ?? "Drill into year by quarter"}</h3>}
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <section style={{ padding: "0.75rem 0.85rem", background: "#fff7ed", borderRadius: 10, border: "1px solid #fed7aa" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <h3 style={{ margin: 0, fontSize: "0.95rem" }}>Cube Operations Agent</h3>
                  <span style={{ fontSize: "0.7rem", color: "#92400e" }}>Slice · Dice · Pivot</span>
                </div>
                {cubeResult ? (
                  <><p style={{ margin: "0 0 0.4rem 0", fontSize: "0.8rem", fontWeight: 600 }}>Operation: {cubeResult.operation || cubeResult.type || "dice"}</p>
                    {renderTable(cubeData, cubeCols, false, formattingRules)}</>
                ) : (
                  <p style={{ margin: 0, color: "#92400e", fontStyle: "italic", fontSize: "0.8rem" }}>Not used for this query.</p>
                )}
              </section>
              <section style={{ padding: "0.75rem 0.85rem", background: "#f5f3ff", borderRadius: 10, border: "1px solid #ddd6fe" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <h3 style={{ margin: 0, fontSize: "0.95rem" }}>KPI Calculator Agent</h3>
                  <span style={{ fontSize: "0.7rem", color: "#5b21b6" }}>Growth · Margins · Top N</span>
                </div>
                {(kpiResult || res?.kpi_data) ? (
                  <><p style={{ margin: "0 0 0.35rem 0", fontSize: "0.8rem", fontWeight: 600 }}>Applied: {kpiResult?.kpi_type || "yoy_growth"}</p>
                    {bestPerformer && <p style={{ margin: "0 0 0.4rem 0", fontSize: "0.8rem" }}>Best performer: <strong>{bestPerformer.region ?? bestPerformer.date_year ?? Object.values(bestPerformer)[0]}</strong></p>}
                    {renderTable(table.length ? table : (res?.kpi_data ?? []), columns, true, formattingRules)}</>
                ) : (
                  <p style={{ margin: 0, color: "#5b21b6", fontStyle: "italic", fontSize: "0.8rem" }}>Not used for this query.</p>
                )}
              </section>
              {chartData.length > 0 && (
                <section style={{ padding: "0.75rem 0.85rem", background: "#f9fafb", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                  <h3 style={{ margin: "0 0 0.4rem 0", fontSize: "0.9rem" }}>Chart – {chartTitle}</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(v) => Number(v).toFixed(2)} />
                      <Legend />
                      <Bar dataKey="value" name={measureLabel} fill="#2563eb" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="growth" name="Growth" fill="#059669" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </section>
              )}
              <section style={{ padding: "0.75rem 0.85rem", background: "#eff6ff", borderRadius: 10, border: "1px solid #bfdbfe" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <h3 style={{ margin: 0, fontSize: "0.95rem" }}>Dimension Navigator Agent</h3>
                  <span style={{ fontSize: "0.7rem", color: "#1e40af" }}>Drill-down · Roll-up</span>
                </div>
                {drill ? (
                  <><p style={{ margin: "0 0 0.35rem 0", fontSize: "0.8rem" }}>Current level: <strong>{drill.current_level}</strong> → Next level: <strong>{drill.next_level}</strong></p>
                    {drill.members?.length > 0 && <p style={{ margin: 0, fontSize: "0.8rem" }}>Members: {drill.members.map((m) => m.value).join(", ")}</p>}</>
                ) : (
                  <p style={{ margin: 0, color: "#1e40af", fontStyle: "italic", fontSize: "0.8rem" }}>Not used for this query.</p>
                )}
              </section>
              <section style={{ padding: "0.75rem 0.85rem", background: "#ecfdf5", borderRadius: 10, border: "1px solid #bbf7d0" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <h3 style={{ margin: 0, fontSize: "0.95rem" }}>Report Generator Agent</h3>
                  <span style={{ fontSize: "0.7rem", color: "#047857" }}>Summary · Totals · Formatting</span>
                </div>
                {report ? (
                  <><h4 style={{ margin: "0 0 0.35rem 0", fontSize: "0.85rem" }}>Executive summary</h4>
                    <p style={{ margin: "0 0 0.6rem 0", fontSize: "0.85rem" }}>{report.summary}</p>
                    {Object.keys(totals).length > 0 && (
                      <><h4 style={{ margin: "0 0 0.3rem 0", fontSize: "0.85rem" }}>Totals</h4>
                        <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.8rem" }}>
                          {Object.entries(totals).map(([k, v]) => (
                            <span key={k} style={{ marginRight: "0.8rem" }}><strong>{k}:</strong> {typeof v === "number" ? v.toFixed(4) : String(v)}</span>
                          ))}
                        </p></>
                    )}
                    {formattingRules.length > 0 && <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.8rem", color: "#047857" }}>Formatting: positive = green, negative = red for growth/margin columns.</p>}
                    <h4 style={{ margin: "0 0 0.4rem 0", fontSize: "0.85rem" }}>Formatted table</h4>
                    {table.length === 0 ? <p style={{ margin: 0, fontSize: "0.8rem" }}>No rows.</p> : renderTable(table, columns, true, formattingRules)}
                  </>
                ) : (
                  <p style={{ margin: 0, color: "#065f46", fontStyle: "italic", fontSize: "0.8rem" }}>Not used for this query.</p>
                )}
              </section>
            </div>
          </div>
        </div>
      </React.Fragment>
    );
  }

  return (
    <div
      style={{
        fontFamily: "system-ui, sans-serif",
        minHeight: "100vh",
        background: "linear-gradient(135deg, #e0f2fe, #eef2ff)",
        display: "flex",
        justifyContent: "center",
        alignItems: "stretch",
        padding: "1.5rem",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 1000,
          background: "white",
          borderRadius: 16,
          boxShadow: "0 20px 40px rgba(15, 23, 42, 0.15)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <header
          style={{
            padding: "1rem 1.5rem",
            borderBottom: "1px solid #e5e7eb",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "linear-gradient(120deg, #1d4ed8, #4f46e5)",
            color: "white",
          }}
        >
          <div>
            <div style={{ fontSize: "0.8rem", opacity: 0.9 }}>OLAP BI</div>
            <h2 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 600 }}>AI Analytics Assistant</h2>
            <p style={{ margin: "0.2rem 0 0 0", fontSize: "0.8rem", opacity: 0.9 }}>
              Ask questions in natural language · Slice, Dice, Drill-down, KPIs, Reports
            </p>
          </div>
          <div style={{ padding: "0.35rem 0.75rem", borderRadius: 999, background: "rgba(15, 23, 42, 0.25)", fontSize: "0.75rem" }}>
            ● Online
          </div>
        </header>

        {/* Chat area */}
        <main
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            padding: "1rem 1.5rem",
            gap: "1rem",
            overflowY: "auto",
          }}
        >
          {error && (
            <div style={{ alignSelf: "center", maxWidth: "70%", padding: "0.75rem 1rem", borderRadius: 999, background: "#fee2e2", color: "#991b1b", fontSize: "0.9rem" }}>
              {error}
            </div>
          )}

          {/* Chat history: all questions and results */}
          {conversationHistory.map((item, index) =>
            renderExchange(item, index, index === conversationHistory.length - 1)
          )}

          {/* Pending query: user asked, waiting for response */}
          {pendingQuery && (
            <>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <div style={{ maxWidth: "75%", background: "#2563eb", color: "white", padding: "0.75rem 1rem", borderRadius: "18px 18px 4px 18px", fontSize: "0.95rem", boxShadow: "0 4px 10px rgba(37, 99, 235, 0.3)" }}>
                  {pendingQuery}
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div style={{ padding: "1rem", background: "#f8fafc", borderRadius: "18px 18px 18px 4px", border: "1px solid #e2e8f0", color: "#64748b", fontSize: "0.9rem" }}>
                  Analyzing…
                </div>
              </div>
            </>
          )}

          <div ref={chatEndRef} />
        </main>

        {/* Composer */}
        <form
          onSubmit={runChatQuery}
          style={{
            padding: "0.85rem 1.5rem 1rem",
            borderTop: "1px solid #e5e7eb",
            background: "#f9fafb",
          }}
        >
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask me anything about your sales cube…"
              style={{
                flex: 1,
                padding: "0.6rem 0.8rem",
                borderRadius: 999,
                border: "1px solid #d1d5db",
                fontSize: "0.9rem",
              }}
            />
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: "0.55rem 1.1rem",
                fontWeight: 600,
                borderRadius: 999,
                border: "none",
                background: loading ? "#9ca3af" : "#2563eb",
                color: "white",
                cursor: loading ? "default" : "pointer",
                fontSize: "0.9rem",
              }}
            >
              {loading ? "Analyzing…" : "Ask"}
            </button>
            {(conversationHistory.length > 0 || pendingQuery) && (
              <button
                type="button"
                onClick={clearChat}
                style={{
                  padding: "0.55rem 1rem",
                  borderRadius: 999,
                  border: "1px solid #d1d5db",
                  background: "white",
                  color: "#6b7280",
                  fontSize: "0.9rem",
                  cursor: "pointer",
                }}
              >
                Clear
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
