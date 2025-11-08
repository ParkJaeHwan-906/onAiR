import { useLocation, useNavigate } from "react-router-dom";
import { LiveKitRoom } from "@livekit/components-react";
import VideoFrame from "../components/Communication/VideoFrame";
import WorkerPanel from "../components/Communication/WorkerPanel";
import { useWebRtcRequestStore } from "../store/useWebRtcRequestStore";
import type { DrawingLine } from "../types/DrawingLine";
import "../styles/Communication/CommunicationPage.css";

export const CommunicationPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { token, partnerInfo } = location.state || {};
  const { completeRequest, completeSentRequest } = useWebRtcRequestStore();

  const handleSerialize = (lines: DrawingLine[]) => {
    const json = JSON.stringify(lines);
    console.log(json);
  };

  // 통신 종료 핸들러
  const handleEndCall = () => {
    // 받은 요청 완료 처리
    if (partnerInfo?.senderAccountId) {
      completeRequest(partnerInfo.senderAccountId);
    }

    // 보낸 요청 완료 처리
    completeSentRequest();

    // 홈으로 이동
    navigate("/home", { replace: true });
  };

  if (!token) return <p>LiveKit 토큰이 없습니다.</p>;

  return (
    <div className="communication-container">
      <LiveKitRoom
        token={token}
        serverUrl="wss://onair-tbfd0pr1.livekit.cloud" // LiveKit 서버 URL
        connect={true}
      >
        <VideoFrame
          handleSerialize={handleSerialize}
          onEndCall={handleEndCall}
        />
      </LiveKitRoom>

      <WorkerPanel partnerInfo={partnerInfo} />
    </div>
  );
};
