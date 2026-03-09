import { useEffect, useState } from "react";
import { api } from "../api";
import { clearInbox } from "../api";
import { Link } from "react-router-dom";

function statusDot(status) {
  if (status?.includes("REVIEW")) return "warn";
  if (status?.includes("FAILED")) return "bad";
  if (status?.includes("SENT") || status?.includes("CREATED")) return "good";
  return "dot";
}

export default function Inbox() {
  const [emails, setEmails] = useState([]);
  const [clearing, setClearing] = useState(false);

  async function load() {
    const res = await api.get("/emails");
    setEmails(res.data);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  async function handleClearInbox() {
    if (
      !window.confirm(
        "Are you sure you want to clear the entire inbox?\nThis will delete all emails and cannot be undone."
      )
    )
      return;

    setClearing(true);
    try {
      await clearInbox();
      setEmails([]);
    } catch (err) {
      alert(
        "Failed to clear inbox: " +
          (err.response?.data?.detail || err.message)
      );
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <div className="cardHeader">
          <div>
            <h1 className="title">Inbox</h1>
            <p className="sub">Auto-refresh every 5 seconds. New emails will appear here.</p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={load}>
              Refresh
            </button>
            <button
              onClick={handleClearInbox}
              disabled={clearing}
              style={{
                background: clearing ? "#999" : "#c0392b",
                color: "white",
                border: "none",
                padding: "8px 16px",
                borderRadius: "6px",
                cursor: clearing ? "not-allowed" : "pointer",
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              {clearing ? "Clearing..." : "🗑 Clear Inbox"}
            </button>
          </div>
        </div>

        <table className="table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Status</th>
              <th>Subject</th>
              <th>From</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {emails.map((e) => (
              <tr key={e.id}>
                <td>
                  <span className="badge">
                    <span className={`dot ${statusDot(e.status)}`} />
                    {e.status}
                  </span>
                </td>
                <td>{e.subject || "(no subject)"}</td>
                <td className="mono">{e.from_email}</td>
                <td>
                  <Link className="tab active" to={`/emails/${e.id}`}>
                    Open
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {emails.length === 0 ? (
          <p className="sub" style={{ marginTop: 12 }}>
            No emails yet.
          </p>
        ) : null}
      </div>
    </div>
  );
}