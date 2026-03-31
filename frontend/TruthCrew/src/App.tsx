import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import NetworkBackground from "./components/NetworkBackground";
import Navigation from "./components/Navigation";
import Index from "./pages/Index";
import Analyze from "./pages/Analyze";
import About from "./pages/About";
import Trending from "./pages/Trending";
import MediaVerification from "./pages/MediaVerification";
import NotFound from "./pages/NotFound";
import TelegramWidget from "./components/TelegramWidget";
import Footer from "./components/Footer";

const App = () => (
  <TooltipProvider>
    <Toaster />
    <Sonner />
    <BrowserRouter>
      <div className="relative min-h-screen">
        <NetworkBackground />
        <Navigation />
        <main className="relative z-10">
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/analyze" element={<Analyze />} />
            <Route path="/about" element={<About />} />
            <Route path="/trending" element={<Trending />} />
            <Route path="/media" element={<MediaVerification />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <Footer />
        <TelegramWidget />
      </div>
    </BrowserRouter>
  </TooltipProvider>
);

export default App;
