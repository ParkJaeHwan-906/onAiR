import { useState } from "react";
import CameraGrid from "../components/CCTV/CameraGrid";
import CameraDetail from "../components/CCTV/CameraDetail";
import type { CCTVItem } from "../types/cctv";
import { useUserStore } from "../store/useUserStore";
import "../styles/CCTV.css";

function CCTVPage() {
  const [selectedCamera, setSelectedCamera] = useState<CCTVItem | null>(null);
  const { myInfo } = useUserStore();
  const isAdmin = myInfo?.role === "관리자";

  /* -------------------------------------------------
    관리자 아닌 경우 — 권한 없음 화면 렌더링
  --------------------------------------------------*/
  if (!isAdmin) {
    return (
      <div className="equipment-page-wrapper empty">
        <div className="equipment-access-card">
          <h2 className="equipment-access-title">접근 권한이 없습니다.</h2>
          <p className="equipment-access-sub">
            CCTV 모니터링은 관리자만 이용할 수 있습니다.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="cctv-page-container">
      {!selectedCamera && (
        <CameraGrid onSelect={(camera) => setSelectedCamera(camera)} />
      )}

      {selectedCamera && (
        <CameraDetail
          camera={selectedCamera}
          onClose={() => setSelectedCamera(null)}
        />
      )}
    </div>
  );
}

export default CCTVPage;
