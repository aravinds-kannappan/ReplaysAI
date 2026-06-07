import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider } from "@clerk/clerk-react";
import "./index.css";
import App from "./App.tsx";

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!PUBLISHABLE_KEY) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <main className="auth-page" style={{ padding: 24, textAlign: "center" }}>
        <div>
          <h1>ReplaysAI needs Clerk config</h1>
          <p className="empty-state">
            Add VITE_CLERK_PUBLISHABLE_KEY to frontend/.env.local to run the authenticated app.
          </p>
        </div>
      </main>
    </StrictMode>
  );
} else {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignInUrl="/onboarding" afterSignUpUrl="/onboarding">
        <App />
      </ClerkProvider>
    </StrictMode>
  );
}
