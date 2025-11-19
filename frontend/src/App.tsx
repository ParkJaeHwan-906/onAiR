import "./App.css";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/Layout/AppLayout";
import HomePage from "./pages/HomePage";
import EmployeePage from "./pages/EmployeePage";
import WorkPage from "./pages/WorkPage";
import EquipmentPage from "./pages/EquipmentPage";
import { CommunicationPage } from "./pages/CommunicationPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import BackdoorPage from "./pages/BackdoorPage";
import { useEffect } from "react";
import { useAuthStore } from "./store/useAuthStore";
import { SocketProvider } from "./utils/socketContext";
import { useSSEStore } from "./store/useSSEStore";
import CCTVPage from "./pages/CCTVPage";

function App() {
  const restoreSession = useAuthStore((state) => state.restoreSession);
  const isRestoring = useAuthStore((state) => state.isRestoring);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const { connect, disconnect } = useSSEStore();

  useEffect(() => {
    const initAuth = async () => {
      await restoreSession();
    };
    initAuth();
  }, [restoreSession]);

  // 로그인 후 자동 SSE 연결
  useEffect(() => {
    if (isAuthenticated) {
      console.log("🔌 [App] SSE Connect");
      connect();
    } else {
      console.log("🔌 [App] SSE Disconnect");
      disconnect();
    }
  }, [isAuthenticated, connect, disconnect]);

  if (isRestoring) return null;

  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="signup" element={<SignupPage />} />
      <Route
        element={
          <SocketProvider>
            <AppLayout />
          </SocketProvider>
        }
      >
        <Route path="home" element={<HomePage />} />
        <Route path="communication" element={<CommunicationPage />} />
        <Route path="employees" element={<EmployeePage />} />
        <Route path="work" element={<WorkPage />} />
        <Route path="equipment" element={<EquipmentPage />} />
        <Route path="backdoor" element={<BackdoorPage />} />
        <Route path="*" element={<Navigate to="/home" replace />} />
        <Route path="cctv" element={<CCTVPage />} />
        <Route path="anomaly" element={<BackdoorPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
