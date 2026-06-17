import { j as jsxRuntimeExports } from "./markdown-CZmKipT5.js";
import { u as useAuth, I as Icon } from "./index-DIoWrWjG.js";
import "./vendor-CPzzSAOr.js";
function LoginGate({ children }) {
  const { user, loading, login } = useAuth();
  if (loading) {
    return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { role: "status", "aria-live": "polite", style: {
      minHeight: "100vh",
      background: "var(--bg)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 20
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { "aria-hidden": "true", style: {
        width: 32,
        height: 32,
        border: "2.5px solid var(--border)",
        borderTopColor: "var(--accent)",
        borderRadius: "50%",
        animation: "spin 0.7s linear infinite"
      } }),
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: { color: "var(--text-dim)", fontSize: 14, fontWeight: 500, letterSpacing: "0.2px" }, children: "Loading DevBuddy" })
    ] });
  }
  if (user) {
    return /* @__PURE__ */ jsxRuntimeExports.jsx(jsxRuntimeExports.Fragment, { children });
  }
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
    minHeight: "100vh",
    background: "var(--bg)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px",
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
  }, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx(
      "a",
      {
        href: "#main-content",
        style: {
          position: "absolute",
          top: "-40px",
          left: "50%",
          transform: "translateX(-50%)",
          background: "var(--accent)",
          color: "white",
          padding: "8px 16px",
          borderRadius: "var(--radius-md)",
          fontSize: "14px",
          fontWeight: 600,
          textDecoration: "none",
          zIndex: 100,
          transition: "top 0.2s ease"
        },
        onFocus: (e) => {
          e.currentTarget.style.top = "12px";
        },
        onBlur: (e) => {
          e.currentTarget.style.top = "-40px";
        },
        children: "Skip to content"
      }
    ),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("main", { id: "main-content", style: {
      width: "100%",
      maxWidth: 360,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 32,
      animation: "fadeInScale 0.4s ease"
    }, children: [
      /* @__PURE__ */ jsxRuntimeExports.jsx("div", { style: {
        width: 48,
        height: 48,
        borderRadius: 14,
        background: "linear-gradient(135deg, var(--accent), var(--accent-hover))",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: "0 4px 16px rgba(99,102,241,0.25)"
      }, children: /* @__PURE__ */ jsxRuntimeExports.jsx(Icon, { name: "sparkles", size: 24, style: { color: "white" } }) }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: { textAlign: "center" }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("h1", { style: {
          fontSize: 24,
          fontWeight: 700,
          color: "var(--text)",
          margin: "0 0 6px",
          letterSpacing: "-0.3px"
        }, children: "Sign in to DevBuddy" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("p", { style: {
          fontSize: 15,
          color: "var(--text-muted)",
          margin: 0,
          lineHeight: 1.5
        }, children: "Your autonomous engineering workspace" })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs(
        "button",
        {
          onClick: login,
          type: "button",
          "aria-label": "Sign in with Google",
          className: "db-btn db-focus",
          style: {
            width: "100%",
            padding: "12px 20px",
            borderRadius: "var(--radius-lg)",
            background: "white",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            fontSize: 15,
            fontWeight: 600,
            color: "var(--bg)",
            transition: "all var(--transition-base)",
            boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
          },
          onMouseEnter: (e) => {
            e.currentTarget.style.transform = "translateY(-1px)";
            e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
          },
          onMouseLeave: (e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.1)";
          },
          children: [
            /* @__PURE__ */ jsxRuntimeExports.jsxs("svg", { width: "18", height: "18", viewBox: "0 0 48 48", "aria-hidden": "true", children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("path", { fill: "#EA4335", d: "M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("path", { fill: "#4285F4", d: "M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("path", { fill: "#FBBC05", d: "M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("path", { fill: "#34A853", d: "M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" })
            ] }),
            "Continue with Google"
          ]
        }
      ),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { style: {
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12
      }, children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("p", { style: {
          fontSize: 13,
          color: "var(--text-faint)",
          textAlign: "center",
          lineHeight: 1.5,
          margin: 0
        }, children: [
          "By continuing, you agree to our",
          " ",
          /* @__PURE__ */ jsxRuntimeExports.jsx("a", { href: "#", style: { color: "var(--accent-light)", textDecoration: "none" }, children: "Terms" }),
          " ",
          "and",
          " ",
          /* @__PURE__ */ jsxRuntimeExports.jsx("a", { href: "#", style: { color: "var(--accent-light)", textDecoration: "none" }, children: "Privacy" }),
          "."
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(
          "a",
          {
            href: "/",
            style: {
              fontSize: 13,
              color: "var(--text-dim)",
              textDecoration: "none",
              transition: "color var(--transition-fast)"
            },
            onMouseEnter: (e) => {
              e.currentTarget.style.color = "var(--text-muted)";
            },
            onMouseLeave: (e) => {
              e.currentTarget.style.color = "var(--text-dim)";
            },
            children: "Learn more about DevBuddy"
          }
        )
      ] })
    ] })
  ] });
}
export {
  LoginGate as default
};
