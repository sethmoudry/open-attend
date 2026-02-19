import { useEffect, lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import LandingPage from "./pages/LandingPage";
import VisitSetup from "./pages/VisitSetup";
import InRoomLayout from "./pages/InRoomLayout";
import PostVisitLayout from "./pages/PostVisitLayout";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));

export default function App() {
  // Global handler for unhandled promise rejections
  useEffect(() => {
    const handler = (event: PromiseRejectionEvent) => {
      console.error("[Unhandled Rejection]", event.reason);
      // Prevent the default browser logging (we already logged it)
      event.preventDefault();
    };
    window.addEventListener("unhandledrejection", handler);
    return () => window.removeEventListener("unhandledrejection", handler);
  }, []);

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/setup" element={<VisitSetup />} />
        <Route path="/dashboard" element={<Suspense fallback={<div className="flex h-screen items-center justify-center text-slate-400">Loading...</div>}><DashboardPage /></Suspense>} />
        <Route path="/session/:id" element={<InRoomLayout />} />
        <Route path="/session/:id/review" element={<PostVisitLayout />} />
      </Routes>
    </ErrorBoundary>
  );
}
