import { useEffect, useState } from "react";
import { api } from "../api";

const FIELD_META = {
  customer_name:      { label: "Customer Name",       placeholder: "e.g. Arjun Mehta",                  type: "text"   },
  weight_kg:          { label: "Weight (kg)",          placeholder: "e.g. 300",                           type: "number" },
  pickup_location:    { label: "Pickup Location",      placeholder: "e.g. Madurai Railway Goods Yard",   type: "text"   },
  drop_location:      { label: "Drop Location",        placeholder: "e.g. Pune Industrial Zone",         type: "text"   },
  pickup_time_window: { label: "Pickup Time Window",   placeholder: "e.g. 2026-03-22 to 2026-03-23",     type: "text"   },
};

const ALL_FIELDS = Object.keys(FIELD_META);

function EmailCard({ email, onSubmitted }) {
  const missing  = email.missing_fields || [];
  const extracted = email.extracted || {};

  // Pre-fill form with already-extracted values; leave missing ones blank
  const initValues = () => {
    const v = {};
    ALL_FIELDS.forEach(k => { v[k] = extracted[k] ?? ""; });
    return v;
  };

  const [values,     setValues]     = useState(initValues);
  const [submitting, setSubmitting] = useState(false);
  const [error,      setError]      = useState("");
  const [expanded,   setExpanded]   = useState(true);

  function handleChange(field, val) {
    setValues(prev => ({ ...prev, [field]: val }));
    setError("");
  }

  async function handleSubmit() {
    // Validate all missing fields are now filled
    const stillEmpty = missing.filter(k => !String(values[k]).trim());
    if (stillEmpty.length > 0) {
      setError(`Please fill in: ${stillEmpty.map(k => FIELD_META[k]?.label || k).join(", ")}`);
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const proposed = {};
      missing.forEach(k => {
        proposed[k] = k === "weight_kg" ? Number(values[k]) : String(values[k]).trim();
      });

      const res = await api.post(`/review/${email.id}/submit`, {
        proposed_fields: proposed,
        reviewer: "human",
      });

      if (res.data.ok) {
        onSubmitted(email.id, res.data);
      } else {
        setError("Submission failed. Please try again.");
      }
    } catch (e) {
      setError(e?.response?.data?.detail || "Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const missingCount = missing.length;

  return (
    <div style={styles.card}>

      {/* ── Card header ── */}
      <div style={styles.cardHeader} onClick={() => setExpanded(e => !e)}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 0 }}>
          {/* Status badge */}
          <div style={styles.missingBadge}>
            <span style={styles.missingDot} />
            {missingCount} missing
          </div>

          <div style={{ minWidth: 0 }}>
            <div style={styles.subject}>{email.subject || "(no subject)"}</div>
            <div style={styles.fromEmail}>{email.from_email}</div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <div style={styles.emailId}>#{email.id}</div>
          <span style={{ color: "rgba(235,255,248,0.4)", fontSize: 18, transition: "transform 0.2s", transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}>▾</span>
        </div>
      </div>

      {/* ── Expanded body ── */}
      {expanded && (
        <div style={styles.cardBody}>

          {/* Field pills row */}
          <div style={styles.pillRow}>
            {ALL_FIELDS.map(k => {
              const isMissing = missing.includes(k);
              const hasValue  = !isMissing && extracted[k];
              return (
                <div key={k} style={{ ...styles.pill, ...(isMissing ? styles.pillMissing : styles.pillOk) }}>
                  <span style={{ marginRight: 4 }}>{isMissing ? "✗" : "✓"}</span>
                  {FIELD_META[k]?.label || k}
                </div>
              );
            })}
          </div>

          {/* Email body preview */}
          {email.body_text && (
            <div style={styles.bodyPreview}>
              <div style={styles.bodyLabel}>📧 Email Body</div>
              <div style={styles.bodyText}>{email.body_text}</div>
            </div>
          )}

          {/* Input fields — only for missing */}
          <div style={styles.fieldsSection}>
            <div style={styles.fieldsTitle}>Fill in missing fields</div>
            <div style={styles.fieldsGrid}>
              {ALL_FIELDS.map(k => {
                const isMissing = missing.includes(k);
                const meta = FIELD_META[k];
                return (
                  <div key={k} style={styles.fieldRow}>
                    <label style={styles.fieldLabel}>
                      {meta.label}
                      {isMissing
                        ? <span style={styles.requiredTag}>required</span>
                        : <span style={styles.extractedTag}>extracted</span>
                      }
                    </label>
                    <input
                      type={meta.type}
                      placeholder={meta.placeholder}
                      value={values[k]}
                      onChange={e => handleChange(k, e.target.value)}
                      disabled={!isMissing}
                      style={{
                        ...styles.input,
                        ...(isMissing ? styles.inputMissing : styles.inputExtracted),
                      }}
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div style={styles.errorBox}>
              ⚠ {error}
            </div>
          )}

          {/* Submit button */}
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{ ...styles.submitBtn, ...(submitting ? styles.submitBtnDisabled : {}) }}
          >
            {submitting ? (
              <span>⏳ Processing...</span>
            ) : (
              <span>✓ Submit & Create Order</span>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export default function ReviewQueue() {
  const [queue,     setQueue]     = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [submitted, setSubmitted] = useState({}); // emailId -> result

  async function load() {
    setLoading(true);
    try {
      const res = await api.get("/review/queue");
      setQueue(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmitted(emailId, result) {
    setSubmitted(prev => ({ ...prev, [emailId]: result }));
    // Remove from queue after short delay
    setTimeout(() => {
      setQueue(prev => prev.filter(e => e.id !== emailId));
      setSubmitted(prev => { const n = { ...prev }; delete n[emailId]; return n; });
    }, 2500);
  }

  useEffect(() => { load(); }, []);

  const activeQueue = queue.filter(e => !submitted[e.id]);

  return (
    <div className="container">
      <div style={styles.pageHeader}>
        <div>
          <h1 className="title">Human Review Queue</h1>
          <p className="sub">
            Emails where AI extraction was incomplete — fill in the missing fields to create the order.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {activeQueue.length > 0 && (
            <div style={styles.queueCount}>
              {activeQueue.length} pending
            </div>
          )}
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Loading..." : "↻ Refresh"}
          </button>
        </div>
      </div>

      {/* Success toasts */}
      {Object.entries(submitted).map(([id, result]) => (
        <div key={id} style={styles.successToast}>
          ✅ Email #{id} — Order created successfully!
          {result.status && <span style={{ opacity: 0.7, marginLeft: 8 }}>Status: {result.status}</span>}
        </div>
      ))}

      {loading && activeQueue.length === 0 ? (
        <div style={styles.emptyState}>Loading...</div>
      ) : activeQueue.length === 0 ? (
        <div style={styles.emptyState}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✓</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 6 }}>Queue is clear</div>
          <div style={{ opacity: 0.5 }}>All emails have been processed successfully.</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {activeQueue.map(email => (
            <EmailCard
              key={email.id}
              email={email}
              onSubmitted={handleSubmitted}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────
const styles = {
  pageHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 24,
    flexWrap: "wrap",
    gap: 12,
  },
  queueCount: {
    background: "rgba(245,158,11,0.15)",
    border: "1px solid rgba(245,158,11,0.4)",
    color: "#f59e0b",
    borderRadius: 20,
    padding: "4px 14px",
    fontSize: 13,
    fontWeight: 600,
  },
  card: {
    background: "rgba(15,20,40,0.7)",
    border: "1px solid rgba(124,255,220,0.12)",
    borderRadius: 16,
    overflow: "hidden",
    transition: "border-color 0.2s",
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 20px",
    cursor: "pointer",
    userSelect: "none",
    borderBottom: "1px solid rgba(124,255,220,0.07)",
    gap: 12,
  },
  missingBadge: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: "rgba(245,158,11,0.15)",
    border: "1px solid rgba(245,158,11,0.35)",
    borderRadius: 20,
    padding: "3px 10px",
    fontSize: 12,
    color: "#f59e0b",
    fontWeight: 600,
    flexShrink: 0,
  },
  missingDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#f59e0b",
    display: "inline-block",
  },
  subject: {
    fontSize: 15,
    fontWeight: 600,
    color: "rgba(235,255,248,0.9)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  fromEmail: {
    fontSize: 12,
    color: "rgba(235,255,248,0.45)",
    marginTop: 2,
  },
  emailId: {
    fontSize: 12,
    color: "rgba(235,255,248,0.3)",
    fontFamily: "monospace",
  },
  cardBody: {
    padding: "20px 20px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 18,
  },
  pillRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  pill: {
    borderRadius: 20,
    padding: "4px 12px",
    fontSize: 12,
    fontWeight: 500,
    display: "flex",
    alignItems: "center",
  },
  pillMissing: {
    background: "rgba(239,68,68,0.12)",
    border: "1px solid rgba(239,68,68,0.35)",
    color: "#f87171",
  },
  pillOk: {
    background: "rgba(34,197,94,0.1)",
    border: "1px solid rgba(34,197,94,0.25)",
    color: "#4ade80",
  },
  bodyPreview: {
    background: "rgba(0,0,0,0.25)",
    border: "1px solid rgba(124,255,220,0.08)",
    borderRadius: 10,
    padding: "12px 14px",
  },
  bodyLabel: {
    fontSize: 11,
    color: "rgba(235,255,248,0.4)",
    marginBottom: 8,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  bodyText: {
    fontSize: 13,
    color: "rgba(235,255,248,0.7)",
    whiteSpace: "pre-wrap",
    lineHeight: 1.6,
    maxHeight: 120,
    overflowY: "auto",
  },
  fieldsSection: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  fieldsTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: "rgba(235,255,248,0.6)",
    textTransform: "uppercase",
    letterSpacing: "0.07em",
  },
  fieldsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
    gap: 12,
  },
  fieldRow: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  fieldLabel: {
    fontSize: 12,
    color: "rgba(235,255,248,0.6)",
    fontWeight: 500,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  requiredTag: {
    background: "rgba(239,68,68,0.15)",
    color: "#f87171",
    border: "1px solid rgba(239,68,68,0.3)",
    borderRadius: 10,
    padding: "1px 7px",
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  extractedTag: {
    background: "rgba(34,197,94,0.1)",
    color: "#4ade80",
    border: "1px solid rgba(34,197,94,0.25)",
    borderRadius: 10,
    padding: "1px 7px",
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  input: {
    borderRadius: 8,
    border: "1px solid",
    padding: "9px 12px",
    fontSize: 14,
    outline: "none",
    transition: "border-color 0.2s, background 0.2s",
    width: "100%",
    boxSizing: "border-box",
    fontFamily: "inherit",
  },
  inputMissing: {
    background: "rgba(15,20,40,0.8)",
    borderColor: "rgba(245,158,11,0.4)",
    color: "rgba(235,255,248,0.9)",
  },
  inputExtracted: {
    background: "rgba(34,197,94,0.04)",
    borderColor: "rgba(34,197,94,0.2)",
    color: "rgba(235,255,248,0.4)",
    cursor: "not-allowed",
  },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid rgba(239,68,68,0.3)",
    borderRadius: 8,
    padding: "10px 14px",
    fontSize: 13,
    color: "#f87171",
  },
  submitBtn: {
    background: "linear-gradient(135deg, rgba(124,255,220,0.15), rgba(46,95,163,0.3))",
    border: "1px solid rgba(124,255,220,0.35)",
    color: "#7CFFDC",
    borderRadius: 10,
    padding: "12px 24px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.2s",
    alignSelf: "flex-start",
    letterSpacing: "0.03em",
  },
  submitBtnDisabled: {
    opacity: 0.5,
    cursor: "not-allowed",
  },
  emptyState: {
    textAlign: "center",
    padding: "60px 20px",
    color: "rgba(235,255,248,0.4)",
  },
  successToast: {
    background: "rgba(34,197,94,0.12)",
    border: "1px solid rgba(34,197,94,0.3)",
    borderRadius: 10,
    padding: "12px 16px",
    fontSize: 14,
    color: "#4ade80",
    marginBottom: 12,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
};