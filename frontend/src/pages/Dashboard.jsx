import { useEffect, useState } from "react";
import { api } from "../api";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from "recharts";

const STATUS_COLORS = {
  RECEIVED:           "#60A5FA",
  EXTRACTING:         "#A78BFA",
  NEEDS_HUMAN_REVIEW: "#f59e0b",
  READY_TO_CONFIRM:   "#7CFFDC",
  ORDER_CREATED:      "#22c55e",
  CONFIRMATION_SENT:  "#10b981",
  FAILED:             "#ef4444",
};

const STATUS_SHORT = {
  RECEIVED:           "Received",
  EXTRACTING:         "Extracting",
  NEEDS_HUMAN_REVIEW: "Needs Review",
  READY_TO_CONFIRM:   "Ready",
  ORDER_CREATED:      "Order Created",
  CONFIRMATION_SENT:  "Confirmed",
  FAILED:             "Failed",
};

function groupByStatus(emails) {
  const counts = {};
  for (const e of emails) {
    counts[e.status] = (counts[e.status] || 0) + 1;
  }
  return Object.entries(counts).map(([status, count]) => ({
    name: STATUS_SHORT[status] || status,
    value: count,
    color: STATUS_COLORS[status] || "#888",
  }));
}

function groupByDay(emails) {
  const days = {};
  for (const e of emails) {
    const d = new Date(e.received_at);
    const key = `${d.getMonth() + 1}/${d.getDate()}`;
    if (!days[key]) days[key] = { date: key, total: 0, orders: 0, failed: 0, review: 0 };
    days[key].total++;
    if (e.status === "ORDER_CREATED" || e.status === "CONFIRMATION_SENT") days[key].orders++;
    if (e.status === "FAILED") days[key].failed++;
    if (e.status === "NEEDS_HUMAN_REVIEW") days[key].review++;
  }
  return Object.values(days).slice(-10);
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(7,10,18,0.95)",
      border: "1px solid rgba(124,255,220,0.2)",
      borderRadius: 12,
      padding: "10px 14px",
      fontSize: 13,
    }}>
      <p style={{ margin: "0 0 6px", color: "rgba(235,255,248,0.6)", fontSize: 12 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ margin: "2px 0", color: p.color || "#7CFFDC" }}>
          {p.name}: <b>{p.value}</b>
        </p>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const [enabled, setEnabled] = useState(false);
  const [emails, setEmails]   = useState([]);
  const [orders, setOrders]   = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [agentRes, emailRes, orderRes, processedRes] = await Promise.all([
        api.get("/agent/status"),
        api.get("/emails?limit=500"),
        api.get("/orders"),
        api.get("/emails/processed?limit=500"),
      ]);
      setEnabled(agentRes.data.enabled);
      setEmails([...(emailRes.data || []), ...(processedRes.data || [])]);
      setOrders(orderRes.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function start() {
    const res = await api.post("/agent/start");
    setEnabled(res.data.enabled === true);
    load();
  }
  async function stop() {
    const res = await api.post("/agent/stop");
    setEnabled(res.data.enabled === true);
    load();
  }

  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  const statusData = groupByStatus(emails);
  const dailyData  = groupByDay(emails);

  const total       = emails.length;
  const totalOrders = orders.length;
  const needsReview = emails.filter(e => e.status === "NEEDS_HUMAN_REVIEW").length;
  const confirmed   = emails.filter(e => e.status === "CONFIRMATION_SENT").length;
  const failed      = emails.filter(e => e.status === "FAILED").length;
  const successRate = total > 0 ? Math.round((totalOrders / total) * 100) : 0;

  return (
    <div className="container">

      {/* ── Header card ── */}
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="cardHeader">
          <div>
            <h1 className="title">Operations Dashboard</h1>
            <p className="sub">
              IMAP ingest → Regex → Gemini → Human Review → Order + Confirmation
            </p>
          </div>
          <span className="badge">
            <span className={`dot ${enabled ? "good" : "bad"}`} />
            {enabled ? "Agent Running" : "Agent Stopped"}
          </span>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn btnPrimary" onClick={start} disabled={enabled}>Start Agent</button>
          <button className="btn btnDanger"  onClick={stop}  disabled={!enabled}>Stop</button>
          <button className="btn" onClick={load}>Refresh</button>
        </div>
      </div>

      {/* ── KPI row ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 14 }}>
        {[
          { label: "Total Emails",   value: total,        color: "#60A5FA" },
          { label: "Orders Created", value: totalOrders,  color: "#22c55e" },
          { label: "Confirmed",      value: confirmed,    color: "#10b981" },
          { label: "Needs Review",   value: needsReview,  color: "#f59e0b" },
          { label: "Failed",         value: failed,       color: "#ef4444" },
          { label: "Success Rate",   value: `${successRate}%`, color: "#7CFFDC" },
        ].map((k) => (
          <div key={k.label} className="card" style={{ padding: "14px 16px", textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: k.color, lineHeight: 1.1 }}>{loading ? "—" : k.value}</div>
            <div style={{ fontSize: 12, color: "rgba(235,255,248,0.55)", marginTop: 4 }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* ── Charts row ── */}
      <div className="grid2" style={{ marginBottom: 14 }}>

        {/* Area chart — daily volume */}
        <div className="card">
          <h3 style={{ margin: "0 0 14px", fontSize: 15, color: "rgba(235,255,248,0.8)" }}>📈 Daily Email Volume</h3>
          {dailyData.length === 0 ? (
            <div style={{ color: "rgba(235,255,248,0.4)", fontSize: 13, textAlign: "center", padding: "40px 0" }}>No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={dailyData}>
                <defs>
                  <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#60A5FA" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#60A5FA" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="orderGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: "rgba(235,255,248,0.4)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "rgba(235,255,248,0.4)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12, color: "rgba(235,255,248,0.6)" }} />
                <Area type="monotone" dataKey="total"  name="Total"  stroke="#60A5FA" fill="url(#totalGrad)" strokeWidth={2} />
                <Area type="monotone" dataKey="orders" name="Orders" stroke="#22c55e" fill="url(#orderGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Pie chart — status breakdown */}
        <div className="card">
          <h3 style={{ margin: "0 0 14px", fontSize: 15, color: "rgba(235,255,248,0.8)" }}>🥧 Status Breakdown</h3>
          {statusData.length === 0 ? (
            <div style={{ color: "rgba(235,255,248,0.4)", fontSize: 13, textAlign: "center", padding: "40px 0" }}>No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%" cy="50%"
                  innerRadius={55} outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {statusData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="rgba(0,0,0,0.3)" strokeWidth={1} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11, color: "rgba(235,255,248,0.6)" }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Bar chart — daily breakdown ── */}
      <div className="card" style={{ marginBottom: 14 }}>
        <h3 style={{ margin: "0 0 14px", fontSize: 15, color: "rgba(235,255,248,0.8)" }}>📊 Daily Status Breakdown</h3>
        {dailyData.length === 0 ? (
          <div style={{ color: "rgba(235,255,248,0.4)", fontSize: 13, textAlign: "center", padding: "40px 0" }}>No data yet — send some emails to see activity!</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dailyData} barGap={4}>
              <XAxis dataKey="date" tick={{ fill: "rgba(235,255,248,0.4)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "rgba(235,255,248,0.4)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, color: "rgba(235,255,248,0.6)" }} />
              <Bar dataKey="orders" name="Orders"      fill="#22c55e" radius={[6,6,0,0]} />
              <Bar dataKey="review" name="Needs Review" fill="#f59e0b" radius={[6,6,0,0]} />
              <Bar dataKey="failed" name="Failed"      fill="#ef4444" radius={[6,6,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Info cards ── */}
      <div className="kpiRow">
        <div className="kpi">
          <b>⏱ Auto-refresh</b>
          <span>Dashboard updates every 15s</span>
        </div>
        <div className="kpi">
          <b>🤖 Agent tick</b>
          <span>Runs every 15s via APScheduler</span>
        </div>
        <div className="kpi">
          <b>🛡 Fallback safety</b>
          <span>Human review for missing fields</span>
        </div>
        <div className="kpi">
          <b>📧 Email delivery</b>
          <span>Powered by Brevo API</span>
        </div>
      </div>

    </div>
  );
}