import { VideoCanvas } from "../components/Communication/VideoCanvas";
import type { DrawingLine } from "../types/DrawingLine";
import { LiveKitRoom } from "@livekit/components-react";
import VideoFrame from "../components/Communication/VideoFrame";
import WorkerPanel from "../components/Communication/WorkerPanel";
import "../styles/Communication/CommunicationPage.css";

export const CommunicationPage = () => {
  const handleSerialize = (lines : DrawingLine[]) => {
    const json = JSON.stringify(lines)
    console.log(json);    
  }
  const TOKEN : string = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJBUElZRGhEQVVQckxMNDciLCJleHAiOjE3NjIxNDI4NDEsInN1YiI6IjMiLCJuYW1lIjoi6rmA7KSA7ZiBIiwibWV0YWRhdGEiOiJtZXRhZGF0YSIsInZpZGVvIjp7InJvb21Kb2luIjp0cnVlLCJyb29tIjoicm9vbV8yMDI1LTExLTAzVDAzOjU3OjE2Ljg0NDQ1MzYxNCJ9LCJzaXAiOnt9fQ.DjdeFAthS-bZ_rJs_GeGEqS1ZkRjchNqFAHCXdJeUsc"

 
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
