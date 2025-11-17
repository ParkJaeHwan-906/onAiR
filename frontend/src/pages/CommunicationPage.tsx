import { useLocation, useNavigate } from "react-router-dom";
import { LiveKitRoom } from "@livekit/components-react";
import VideoFrame from "../components/Communication/VideoFrame";
import WorkerPanel from "../components/Communication/WorkerPanel";
import { useWebRtcRequestStore } from "../store/useWebRtcRequestStore";
import type { DrawingLine } from "../types/DrawingLine";
import "../styles/Communication/CommunicationPage.css";
import { useEffect } from "react";

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

  useEffect(() => {
    if (!token) {
      // URL 직접 접근 등으로 진입 시 리스트 페이지로 되돌림
      const timeout = window.setTimeout(() => {
        navigate("/communication", { replace: true });
      }, 0);
      return () => window.clearTimeout(timeout);
    }
  }, [token, navigate]);

  if (!token) {
    return (
      <div className="communication-container empty">
        <div className="communication-empty-card">
          <h2 className="communication-empty-title">
            통신 연결을 준비하고 있어요
          </h2>
          <p className="communication-empty-sub">
            승인이 아직 완료되지 않았을 수 있어요. <br />
            다시 요청을 보내거나 새로고침해 주세요.
          </p>
          <div className="communication-empty-actions">
            <button
              type="button"
              className="communication-empty-button"
              onClick={() => navigate("/home", { replace: true })}
            >
              홈으로 이동
            </button>
            <button
              type="button"
              className="communication-empty-secondary"
              onClick={() => window.location.reload()}
            >
              새로고침
            </button>
          </div>
        </div>
      </div>
    );
  }

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
