import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SignIn, SignUp } from "@clerk/clerk-react";
import Navbar from "./components/Navbar";
import FloatingAssistant from "./components/FloatingAssistant";
import ProtectedRoute from "./components/ProtectedRoute";
import Landing from "./pages/Landing";
import Onboarding from "./pages/Onboarding";
import Feed from "./pages/Feed";
import Reels from "./pages/Reels";
import GameDetail from "./pages/GameDetail";
import PlayerProfile from "./pages/PlayerProfile";
import Predictions from "./pages/Predictions";
import Leaderboard from "./pages/Leaderboard";
import RosterBuilder from "./pages/RosterBuilder";
import Profile from "./pages/Profile";
import "./App.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Navbar />
        <Routes>
          {/* Public */}
          <Route path="/" element={<Landing />} />
          <Route path="/sign-in/*" element={<div className="auth-page"><SignIn routing="path" path="/sign-in" /></div>} />
          <Route path="/sign-up/*" element={<div className="auth-page"><SignUp routing="path" path="/sign-up" /></div>} />

          {/* Auth-gated */}
          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/feed" element={<ProtectedRoute><Feed /></ProtectedRoute>} />
          <Route path="/reels" element={<ProtectedRoute><Reels /></ProtectedRoute>} />
          <Route path="/game/:id" element={<ProtectedRoute><GameDetail /></ProtectedRoute>} />
          <Route path="/player/:id" element={<ProtectedRoute><PlayerProfile /></ProtectedRoute>} />
          <Route path="/predictions" element={<ProtectedRoute><Predictions /></ProtectedRoute>} />
          <Route path="/leaderboard" element={<ProtectedRoute><Leaderboard /></ProtectedRoute>} />
          <Route path="/roster" element={<ProtectedRoute><RosterBuilder /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
        </Routes>
        <FloatingAssistant />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
