import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import "./index.css";
import App from "./App.tsx";
import { getDeviceId } from "./lib/device";

// Attach the anonymous device id to every API request so the backend can key
// this fan's picks, points, and leaderboard rank without a login.
axios.defaults.headers.common["X-Device-Id"] = getDeviceId();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
