import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Navbar from "./components/Navbar";
import FloatingAssistant from "./components/FloatingAssistant";
import Landing from "./pages/Landing";
import Onboarding from "./pages/Onboarding";
import Feed from "./pages/Feed";
import DreamTeam from "./pages/DreamTeam";
import ReelStudio from "./pages/ReelStudio";
import GameDetail from "./pages/GameDetail";
import PlayerProfile from "./pages/PlayerProfile";
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
          <Route path="/" element={<Landing />} />
          {/* The demo is the team + player picker; no login required. */}
          <Route path="/demo" element={<Onboarding />} />
          <Route path="/onboarding" element={<Onboarding />} />

          {/* One dashboard — every tab routes here and reads the tab from the path. */}
          <Route path="/feed" element={<Feed />} />
          <Route path="/dashboard" element={<Feed />} />
          <Route path="/season" element={<Feed />} />
          <Route path="/games" element={<Feed />} />
          <Route path="/reels" element={<Feed />} />
          <Route path="/extras" element={<Feed />} />
          <Route path="/picks" element={<Feed />} />
          <Route path="/predictions" element={<Feed />} />
          <Route path="/roster" element={<Feed />} />
          <Route path="/leaderboard" element={<Feed />} />

          {/* Dedicated heavy surfaces (hybrid routing). */}
          <Route path="/dream-team" element={<DreamTeam />} />
          <Route path="/reel/:gameId" element={<ReelStudio />} />

          <Route path="/game/:id" element={<GameDetail />} />
          <Route path="/player/:id" element={<PlayerProfile />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
        <FloatingAssistant />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
