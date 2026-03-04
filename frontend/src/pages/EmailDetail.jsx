import { useEffect, useState } from "react";
import { api } from "../api";
import { useParams } from "react-router-dom";
import FieldTable from "../components/FieldTable";

function getStatusTone(status) {
  if (!status) return "warn";
  if (status === "FAILED") return "bad";
  if (String(status).includes("REVIEW")) return "warn";
  if (status === "EXTRACTING" || status === "RECEIVED") return "warn";
  return "good";
}

export default function EmailDetail() {
  const { id } = useParams();
  const [email, setEmail] = useState(null);

  async function load() {
    const res = await api.get(`/emails/${id}`);
    setEmail(res.data);
  }

  async function processNow() {
    await api.post(`/emails/${id}/process`);
    alert("Processing started. Refresh in a few seconds.");
  }

  useEffect(() => { load(); }, [id]);

  if (!email) return <div className="container"><div className="card">Loading...</div></div>;

  const statusTone = getStatusTone(email.status);
  const isFailed = email.status === "FAILED";
  const hasWarning = !!email.last_error && !isFailed;

  return (
    <div className="container">
      <div className="grid2">
        <div className="card">
          <div className="cardHeader">
            <div>
              <h1 className="title">Email #{email.id}</h1>
              <p className="sub">Extraction + order creation status for this email.</p>
            </div>

            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              {/* ✅ Real status badge */}
              <span className="badge">
                <span className={`dot ${statusTone}`} />
                {email.status}
              </span>

              {/* ✅ Separate warning badge (does NOT imply FAILED) */}
              {hasWarning ? (
                <span className="badge" title="Non-fatal issue (Gemini/SMTP may be skipped)">
                  <span className="dot warn" />
                  WARNING
                </span>
              ) : null}
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <div className="kpi">
              <span className="sub">From</span>
              <b className="mono">{email.from_email}</b>
            </div>

            <div className="kpi" style={{ marginTop: 10 }}>
              <span className="sub">Subject</span>
              <b>{email.subject || "(no subject)"}</b>
            </div>

            {/* ✅ Error box color depends on fatal vs warning */}
            {email.last_error ? (
              <div
                className="kpi"
                style={{
                  marginTop: 10,
                  borderColor: isFailed ? "rgba(239,68,68,.35)" : "rgba(245,158,11,.35)",
                }}
              >
                <span className="sub">{isFailed ? "Error" : "Warning"}</span>
                <b style={{ color: isFailed ? "#fecaca" : "#fde68a" }}>
                  {email.last_error}
                </b>
              </div>
            ) : null}
          </div>

          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn btnPrimary" onClick={processNow}>Run Extraction Now</button>
            <button className="btn" onClick={load}>Refresh</button>
          </div>
        </div>

        <div className="card">
          <h2 className="title" style={{ fontSize: 18 }}>Extracted Fields</h2>
          <FieldTable extracted={email.extracted} missing={email.missing_fields} />
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <h2 className="title" style={{ fontSize: 18 }}>Email Body</h2>
        <pre className="mono" style={{ whiteSpace: "pre-wrap" }}>
{email.body_text || "(empty)"}
        </pre>
      </div>
    </div>
  );
}