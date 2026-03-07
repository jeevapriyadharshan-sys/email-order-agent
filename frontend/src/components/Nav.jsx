import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

const baseTabs = [
  { to: "/", label: "Dashboard" },
  { to: "/activity", label: "Activity" },
  { to: "/inbox", label: "Inbox" },
  { to: "/review", label: "Human Review" },
  { to: "/orders", label: "Orders" },
  { to: "/processed", label: "Processed" },
];

export default function Nav() {
  const loc = useLocation();
  const nav = useNavigate();
  const role = localStorage.getItem("role") || "viewer";
  const [menuOpen, setMenuOpen] = useState(false);

  const tabs = [...baseTabs, ...(role === "admin" ? [{ to: "/settings", label: "Settings" }] : [])];

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    nav("/login");
  }

  function handleTabClick() {
    setMenuOpen(false);
  }

  return (
    <>
      <div className="topbar">
        <div className="navInner">
          {/* Brand */}
          <div className="brand">
            <div className="brandLogo" />
            <div className="brandTitle">
              <b>Email Order Agent</b>
              <span>Cyber Ops Console</span>
            </div>
          </div>

          {/* Desktop tabs */}
          <div className="tabs desktopTabs">
            {tabs.map((t) => (
              <Link key={t.to} to={t.to} className={`tab ${loc.pathname === t.to ? "active" : ""}`}>
                {t.label}
              </Link>
            ))}
          </div>

          <div className="spacer" />

          {/* Desktop right side */}
          <span className="pill desktopOnly">ROLE: {role.toUpperCase()}</span>
          <button className="btn desktopOnly" onClick={logout}>Logout</button>

          {/* Hamburger button - mobile only */}
          <button
            className="hamburger"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <span className={`hamburgerLine ${menuOpen ? "open1" : ""}`} />
            <span className={`hamburgerLine ${menuOpen ? "open2" : ""}`} />
            <span className={`hamburgerLine ${menuOpen ? "open3" : ""}`} />
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="mobileDrawer" onClick={() => setMenuOpen(false)}>
          <div className="mobileDrawerInner" onClick={e => e.stopPropagation()}>
            {/* Role + logout */}
            <div className="mobileDrawerTop">
              <span className="pill">ROLE: {role.toUpperCase()}</span>
              <button className="btn btnDanger" onClick={logout}>Logout</button>
            </div>

            {/* Nav links */}
            <div className="mobileTabs">
              {tabs.map((t) => (
                <Link
                  key={t.to}
                  to={t.to}
                  className={`mobileTab ${loc.pathname === t.to ? "active" : ""}`}
                  onClick={handleTabClick}
                >
                  {t.label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}