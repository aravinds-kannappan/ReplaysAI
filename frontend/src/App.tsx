import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Navbar from "./components/Navbar";
import FloatingAssistant from "./components/FloatingAssistant";
import Landing from "./pages/Landing";
import Onboarding from "./pages/Onboarding";
import Feed from "./pages/Feed";
import ReelStudio from "./pages/ReelStudio";
import ReelsPage from "./pages/ReelsPage";
import BroadcastPlayer from "./pages/BroadcastPlayer";
import NewsletterPage, { NewsletterShare } from "./pages/Newsletter";
import GameDetail from "./pages/GameDetail";
import PlayerProfile from "./pages/PlayerProfile";
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
          <Route path="/demo" element={<Onboarding />} />
          <Route path="/onboarding" element={<Onboarding />} />

          {/* Dashboard tabs */}
          <Route path="/feed" element={<Feed />} />
          <Route path="/dashboard" element={<Feed />} />
          <Route path="/season" element={<Feed />} />
          <Route path="/games" element={<Feed />} />
          <Route path="/stats" element={<Feed />} />
          <Route path="/extras" element={<Feed />} />
          <Route path="/picks" element={<Feed />} />
          <Route path="/predictions" element={<Feed />} />
          <Route path="/roster" element={<Feed />} />
          <Route path="/leaderboard" element={<Feed />} />

          {/* Dedicated surfaces */}
          <Route path="/reels" element={<ReelsPage />} />
          <Route path="/broadcast/:gameId" element={<BroadcastPlayer />} />
          <Route path="/newsletter" element={<NewsletterPage />} />
          <Route path="/newsletter/share/:token" element={<NewsletterShare />} />
          <Route path="/reel/:gameId" element={<ReelStudio />} />

          <Route path="/game/:id" element={<GameDetail />} />
          <Route path="/player/:id" element={<PlayerProfile />} />
        </Routes>
        <FloatingAssistant />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
