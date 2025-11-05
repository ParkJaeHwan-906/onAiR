import type { DrawingLine } from "../types/DrawingLine";
import { LiveKitRoom } from "@livekit/components-react";
import VideoFrame from "../components/Communication/VideoFrame";
import WorkerPanel from "../components/Communication/WorkerPanel";
import "../styles/Communication/CommunicationPage.css";
import { useSocket } from "../utils/socketContext";

export const CommunicationPage = () => {
  const socket = useSocket();   // 연결되어있는 소켓 객체를 가져옴
  const handleSerialize = (lines : DrawingLine[]) => {
    const json = JSON.stringify(lines)
    console.log(json);    
  }
  const TOKEN : string = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJBUElZRGhEQVVQckxMNDciLCJleHAiOjE3NjI4MTk2MTIsInN1YiI6IjMiLCJuYW1lIjoi6rmA7KSA7ZiBIiwibWV0YWRhdGEiOiJtZXRhZGF0YSIsInZpZGVvIjp7InJvb21Kb2luIjp0cnVlLCJyb29tIjoiamhfcm9vbSJ9LCJzaXAiOnt9fQ.e-cTHUTvWe6nD7RtIlPAIH8kD35metbExvv8jbufA4c"

 
  return (
    <div className="communication-container">
      <LiveKitRoom
        token={TOKEN}
        serverUrl="wss://onair-tbfd0pr1.livekit.cloud"
        connect={true}
      >
        <VideoFrame handleSerialize={handleSerialize} />
      </LiveKitRoom>

      <WorkerPanel />
    </div>
  );
};
