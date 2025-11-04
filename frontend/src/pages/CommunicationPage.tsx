import { VideoCanvas } from "../components/Communication/VideoCanvas";
import type { DrawingLine } from "../types/DrawingLine";
import { LiveKitRoom } from "@livekit/components-react";
// import { OverlayCanvas } from "../components/OverlayCanvas"
import VideoFrame from "../components/Communication/VideoFrame";
import WorkerPanel from "../components/Communication/WorkerPanel";
import "../styles/Communication/CommunicationPage.css";

export const CommunicationPage = () => {
  const handleSerialize = (lines: DrawingLine[]) => {
    const json = JSON.stringify(lines);
    console.log(json);
  };

  return (
    <div className="communication-container">
      <LiveKitRoom
        token="<livekit-token>"
        serverUrl="<url-to-livekit-server>"
        connect={true}
      >
        <VideoFrame handleSerialize={handleSerialize} />
      </LiveKitRoom>

      <WorkerPanel />
    </div>
  );
};
