import React from "react";
import type { CCTVItem } from "../../types/cctv";
import { PhoneCall, Headphones, Mic } from "lucide-react";
import "../../styles/CCTV.css";

interface CameraDetailProps {
  camera: CCTVItem;
  onClose: () => void;
}

const CameraDetail: React.FC<CameraDetailProps> = ({ camera, onClose }) => {
  return (
    <div className="detail-view">
      <button className="detail-close-inline" onClick={onClose}>
        ✕
      </button>

      <div className="detail-video-box">
        <video
          src={camera.videoUrl}
          autoPlay
          muted
          loop
          playsInline
          className="detail-video-inline"
        />

        {/* 좌하단 : 라벨 + 버튼 한 줄 구성 */}
        <div className="detail-info-inline">
          <div className="detail-label-inline">
            {camera.worker.name} | {camera.equipment.name}
          </div>

          <div className="detail-inline-buttons">
            <button className="detail-ctrl-btn call">
              <PhoneCall size={16} />
            </button>
            <button className="detail-ctrl-btn listen">
              <Headphones size={16} />
            </button>
            <button className="detail-ctrl-btn talk">
              <Mic size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CameraDetail;
