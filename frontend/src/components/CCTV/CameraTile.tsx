import React from "react";
import "../../styles/CCTV.css";
import type { CCTVItem } from "../../types/cctv";

interface CameraTileProps {
  camera: CCTVItem;
  onClick: () => void;
}

const CameraTile: React.FC<CameraTileProps> = ({ camera, onClick }) => {
  return (
    <div className="cctv-tile" onClick={onClick}>
      <video
        src={camera.videoUrl}
        className="cctv-video"
        muted // 브라우저 정책으로 추가 없음 autoPlay 안됌
        autoPlay // 영상 자동 재생
        loop // 반복
        playsInline // 모바일용 인라인 플레이
      />
      <div className="cctv-label">
        {camera.worker.name} | {camera.equipment.name}
      </div>
    </div>
  );
};

export default CameraTile;
