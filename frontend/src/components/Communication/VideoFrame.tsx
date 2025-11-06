import { useState } from "react";
import { VideoCanvas } from "./VideoCanvas"; // 비디오 박스
import ControlBar from "./ControlBar";
import type { DrawingLine } from "../../types/DrawingLine";
import "../../styles/Communication/VideoFrame.css";

interface VideoFrameProps {
  handleSerialize: (lines: DrawingLine[]) => void;
}

const VideoFrame = ({ handleSerialize }: VideoFrameProps) => {
  const [currentTool, setCurrentTool] = useState<string>(""); // 펜, 도형, 지우개
  const [penColor, setPenColor] = useState("#000000");

  return (
    <div className="video-frame">
      <div className="video-canvas-wrap">
        <VideoCanvas
          handleSerialize={handleSerialize}
          penColor={penColor}
          currentTool={currentTool}
        />
      </div>
      <div className="control-bar-wrap">
        <ControlBar
          currentTool={currentTool}
          setCurrentTool={setCurrentTool}
          penColor={penColor}
          setPenColor={setPenColor}
        />
      </div>
    </div>
  );
};

export default VideoFrame;
