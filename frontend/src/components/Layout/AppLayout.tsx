import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import "../../styles/AppLayout.css";
import SideBar from "../SideBar/SideBar";
import TopBar from "../TopBar/TopBar";
import { useSSEStore } from "../../store/useSSEStore";

function AppLayout() {
  const { connect, disconnect } = useSSEStore();

  // AppLayout이 마운트될 때 SSE 연결
  useEffect(() => {
    console.log("🏠 AppLayout 마운트 - SSE 연결 시작");
    connect();

    // 언마운트될 때 SSE 연결 종료
    return () => {
      console.log("🏠 AppLayout 언마운트 - SSE 연결 종료");
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 한 번만 실행

  return (
    <div className="app-layout">
      <SideBar />
      <div className="app-layout-content">
        <TopBar />
        <main className="app-layout-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppLayout;
