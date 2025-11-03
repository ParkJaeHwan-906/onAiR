import "./App.css";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/Layout/AppLayout";
import HomePage from "./pages/HomePage";
import EmployeePage from "./pages/EmployeePage";
import WorkPage from "./pages/WorkPage";
import { CommunicationPage } from "./pages/CommunicationPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import { useEffect } from "react";
import { useAuthStore } from "./store/useAuthStore";

function App() {
  const restoreSession = useAuthStore((state) => state.restoreSession);
  const isRestoring = useAuthStore((state) => state.isRestoring);

  useEffect(() => {
    const initAuth = async () => {
      await restoreSession();
    };
    initAuth();
  }, [restoreSession]);

  if (isRestoring) return null;

  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="signup" element={<SignupPage />} />
      <Route element={<AppLayout />}>
        <Route path="home" element={<HomePage />} />
        <Route path="communication" element={<CommunicationPage />} />
        <Route path="employees" element={<EmployeePage />} />
        <Route path="work" element={<WorkPage />} />
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
