import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/inter-tight";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import App from "./App";
import { AdminApp } from "./admin/AdminApp";
import { TripPage } from "./trip/TripPage";

const path = window.location.pathname.replace(/\/$/, "");
const isAdmin = path === "/admin";
const tripMatch = path.match(/^\/t\/([^/]+)$/);

function Root() {
  if (isAdmin) return <AdminApp />;
  if (tripMatch) return <TripPage token={tripMatch[1]} />;
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
