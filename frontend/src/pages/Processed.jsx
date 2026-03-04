import { useEffect, useState } from "react";
import { api } from "../api";
import { Link } from "react-router-dom";

export default function Processed() {
  const [items, setItems] = useState([]);

  async function load(){
    const res = await api.get("/emails/processed");
    setItems(res.data || []);
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="container">
      <div className="card">
        <div className="cardHeader">
          <div>
            <h1 className="title">Processed</h1>
            <p className="sub">Archived emails for which orders were created.</p>
          </div>
          <button className="btn" onClick={load}>Refresh</button>
        </div>

        <table className="table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>ID</th>
              <th>From</th>
              <th>Subject</th>
              <th>Status</th>
              <th>Open</th>
            </tr>
          </thead>
          <tbody>
            {items.map(e => (
              <tr key={e.id}>
                <td className="mono">{e.id}</td>
                <td className="mono">{e.from_email}</td>
                <td>{e.subject || "(no subject)"}</td>
                <td className="mono">{e.status}</td>
                <td><Link className="btn" to={`/emails/${e.id}`}>View</Link></td>
              </tr>
            ))}
          </tbody>
        </table>

        {items.length === 0 ? <p className="sub" style={{ marginTop: 12 }}>No processed emails yet.</p> : null}
      </div>
    </div>
  );
}