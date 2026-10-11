import { Navigate, Routes, Route } from "react-router-dom";
import { HomePage } from "./pages/HomePage.jsx";
import { AttendancePage } from "./pages/AttendancePage.jsx";
import { StudentPassPage } from "./pages/StudentPassPage.jsx";
import { LoginPage } from "./pages/LoginPage.jsx";
import { RegisterPage } from "./pages/RegisterPage.jsx";
import { OAuthCallbackPage } from "./pages/OAuthCallbackPage.jsx";
import { DashboardPage } from "./pages/DashboardPage.jsx";
import { EventCatalogPage } from "./pages/EventCatalogPage.jsx";
import { StudentODPage } from "./pages/StudentODPage.jsx";
import { useAuth } from "./auth/AuthProvider.jsx";
import { roleHomePath } from "./auth/rolePolicy.js";

function NotFoundPage() {
  return <main className="mx-auto max-w-2xl px-6 py-24 text-center"><h1 className="text-4xl font-black text-ink">Page not found</h1><p className="mt-3 text-slate-600">The page you requested does not exist in this preview.</p></main>;
}

function PublicEntry({ children }) {
  const { loading, profile } = useAuth();
  if (loading) return <main className="grid min-h-screen place-items-center bg-mist" aria-label="Restoring session">Loading EventSphere…</main>;
  return profile ? <Navigate to={roleHomePath(profile.role)} replace /> : children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<PublicEntry><HomePage /></PublicEntry>} />
      <Route path="/events/" element={<EventCatalogPage />} />
      <Route path="/student/" element={<DashboardPage role="student" />} />
      <Route path="/organizer/" element={<DashboardPage role="organizer" />} />
      <Route path="/admin/" element={<DashboardPage role="admin" />} />
      <Route path="/organizer/attendance/" element={<AttendancePage />} />
      <Route path="/admin/attendance/" element={<AttendancePage />} />
      <Route path="/student/event-pass/" element={<StudentPassPage />} />
      <Route path="/student/od-letters/" element={<StudentODPage />} />
      <Route path="/login/" element={<PublicEntry><LoginPage /></PublicEntry>} />
      <Route path="/register/" element={<PublicEntry><RegisterPage /></PublicEntry>} />
      <Route path="/auth/callback/" element={<OAuthCallbackPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
