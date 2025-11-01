// import { VideoTrack } from "@livekit/components-react"
import type { DrawingLine } from "../types/DrawingLine";
import { OverlayCanvas } from "./OverlayCanvas";

interface VideoProps {
  handleSerialize: (lines: DrawingLine[]) => void;
  penColor: string;
  currentTool: string;
}

export const VideoCanvas = ({
  handleSerialize,
  penColor,
  currentTool,
}: VideoProps) => {
  return (
    <div
      style={{
        position: "relative",
        width: "940px",
        height: "857px",
        backgroundColor: "#333",
        borderRadius: "16px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          zIndex: 1,
        }}
      >
        {/* <VideoTrack /> */}
        <p style={{ color: "white" }}>(Video)</p>
      </div>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          zIndex: 10,
        }}
      >
        <OverlayCanvas
          handleSerialize={handleSerialize}
          penColor={penColor}
          tool={currentTool}
        />
      </div>
    </div>
  );
};
