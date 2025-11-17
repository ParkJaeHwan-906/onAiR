import React from "react";
import { cctvList } from "./cctvDummyData";
import CameraTile from "./CameraTile";
import type { CCTVItem } from "../../types/cctv";
import "../../styles/CCTV.css";

interface CameraGridProps {
  onSelect: (camera: CCTVItem) => void;
}

const CameraGrid: React.FC<CameraGridProps> = ({ onSelect }) => {
  return (
    <div className="cctv-grid">
      {cctvList.map((camera) => (
        <CameraTile
          key={camera.id}
          camera={camera}
          onClick={() => onSelect(camera)}
        />
      ))}
    </div>
  );
};

export default CameraGrid;
