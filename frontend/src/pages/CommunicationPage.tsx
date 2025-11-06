import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { LiveKitRoom } from "@livekit/components-react";
import { connectSSE, disconnectSSE } from "../api/sse";
import VideoFrame from "../components/Communication/VideoFrame";
import WorkerPanel from "../components/Communication/WorkerPanel";
import type { DrawingLine } from "../types/DrawingLine";
import "../styles/Communication/CommunicationPage.css";

export const CommunicationPage = () => {
  const location = useLocation();
  // const { token, roomName } = location.state || {};
  // const [connected, setConnected] = useState(false);
  const { token } = location.state || {};
  const [, setConnected] = useState(false);

  const handleSerialize = (lines: DrawingLine[]) => {
    const json = JSON.stringify(lines);
    console.log(json);
  };

  useEffect(() => {
    // SSE 연결 시작
    const eventSource = connectSSE((event) => {
      console.log("SSE 이벤트 수신:", event.data);
    });
    setConnected(true);

    //페이지 나갈 때 연결 종료
    return () => {
      disconnectSSE(eventSource);
      setConnected(false);
    };
  }, []);

  if (!token) return <p>LiveKit 토큰이 없습니다.</p>;

  return (
    <div className="communication-container">
      <LiveKitRoom
        token={token}
        serverUrl="ws://localhost:7880" // LiveKit 서버 URL
        connect={true}
      >
        <VideoFrame handleSerialize={handleSerialize} />
      </LiveKitRoom>

      <WorkerPanel />
    </div>
  );
};
