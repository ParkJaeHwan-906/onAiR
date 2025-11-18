import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { sendConnectionRequest } from "../../api/webrtc";
import { useUserStore } from "../../store/useUserStore";
import { useSSEStore } from "../../store/useSSEStore";
import { useSSEEventsStore } from "../../store/useSSEEventsStore";
import { useWebRtcRequestStore } from "../../store/useWebRtcRequestStore";

import type { CCTVItem } from "../../types/cctv";
import { PhoneCall, Headphones, Mic } from "lucide-react";

import { useSocket } from "../../utils/socketContext";
import { VideoBuffer } from "../../utils/VideoBuffer";
import { PlaybackClock } from "../../utils/PlaybackClock";

import "../../styles/CCTV.css";

interface CameraDetailProps {
  camera: CCTVItem;
  onClose: () => void;
}

const CameraDetail: React.FC<CameraDetailProps> = ({ camera, onClose }) => {
  const socket = useSocket();
  const navigate = useNavigate();
  const { events } = useSSEEventsStore();
  const lastEvent = events[events.length - 1];

  const isTargetCamera = camera.id === 1;

  const imgRef = useRef<HTMLImageElement>(null);
  const videoBufferRef = useRef<VideoBuffer | null>(null);
  const clockRef = useRef<PlaybackClock | null>(null);

  const [isLiveConnected, setIsLiveConnected] = useState(false);

  const { myInfo } = useUserStore();
  const { isConnected, connect } = useSSEStore();
  const { addSentRequest } = useWebRtcRequestStore();

  const handleCallRequest = async () => {
    if (!camera.worker) {
      alert("담당자가 없습니다.");
      return;
    }

    // SSE 연결 없으면 재연결
    if (!isConnected) connect();

    const res = await sendConnectionRequest(
      camera.worker.id, // receiverAccountId = 담당자 계정
      "" // description 비우거나 필요한 내용 넣기
    );

    if (!res.success) {
      alert(res.message || "요청 실패");
      return;
    }

    // 내 요청을 store에 기록 (CommunicationPage에서 보여야 하니까)
    if (myInfo) {
      addSentRequest(
        {
          senderAccountId: myInfo.userAccountId,
          name: myInfo.name,
          phone: myInfo.phone || "",
          equipmentName: myInfo.equipmentName || null,
        },
        {
          senderAccountId: camera.worker.id,
          name: camera.worker.name,
          phone: "",
          equipmentName: camera.equipment.name,
        }
      );
    }

    alert("통신 요청이 전송되었습니다.");
  };

  useEffect(() => {
    if (!lastEvent) return;

    if (lastEvent === "callRequest") {
      // 내가 받은 요청이라면 CommunicationPage로 이동
      navigate("/communication");
    }
  }, [lastEvent]);

  /* --------------------------------------------
      LIVE (ID=1만)
  -------------------------------------------- */
  useEffect(() => {
    if (!socket || !isTargetCamera) return;

    const videoBuffer = new VideoBuffer({
      maxBufferSize: 12,
      onFrameReady: (blobUrl) => {
        if (imgRef.current) {
          if (imgRef.current.src.startsWith("blob:")) {
            URL.revokeObjectURL(imgRef.current.src);
          }
          imgRef.current.src = blobUrl;
        }
      },
    });

    videoBufferRef.current = videoBuffer;

    const handleVideoFrame = (data: {
      timestamp: number;
      frame: ArrayBuffer;
    }) => {
      videoBuffer.enqueue(data.timestamp, data.frame);
      if (!isLiveConnected) setIsLiveConnected(true);
    };

    socket.on("video_frame", handleVideoFrame);

    const imgNode = imgRef.current;

    return () => {
      socket.off("video_frame", handleVideoFrame);
      videoBuffer.clear();
      if (imgNode?.src.startsWith("blob:")) URL.revokeObjectURL(imgNode.src);
    };
  }, [socket, isTargetCamera, isLiveConnected]);

  /* --------------------------------------------
      clock (ID=1만)
  -------------------------------------------- */
  useEffect(() => {
    if (!isTargetCamera || !isLiveConnected) return;

    const clock = new PlaybackClock();
    clock.start();
    clockRef.current = clock;

    const interval = setInterval(() => {
      const now = clock.now();
      videoBufferRef.current?.updateClock(now);
    }, 16);

    return () => clearInterval(interval);
  }, [isTargetCamera, isLiveConnected]);

  const isLive = isTargetCamera && isLiveConnected;

  return (
    <div className="detail-view">
      <button className="detail-close-inline" onClick={onClose}>
        ✕
      </button>

      <div className="detail-video-box">
        {isLive ? (
          <>
            <img ref={imgRef} className="detail-video-inline" alt="Live CCTV" />

            <div className="detail-info-inline">
              <div className="detail-label-inline">
                {camera.worker.name} | {camera.equipment.name}
                <span className="live-badge" style={{ marginLeft: 6 }}>
                  ● LIVE
                </span>
              </div>

              <div className="detail-inline-buttons">
                <button
                  className="detail-ctrl-btn call"
                  onClick={handleCallRequest}
                >
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
          </>
        ) : (
          <>
            {/* ID=2~6 또는 1 OFFLINE → 더미 영상 */}
            <video
              src={camera.videoUrl}
              autoPlay
              muted
              loop
              playsInline
              className="detail-video-inline"
            />

            <div className="detail-info-inline">
              <div className="detail-label-inline">
                {camera.worker.name} | {camera.equipment.name}
              </div>

              <div className="detail-inline-buttons">
                <button
                  className="detail-ctrl-btn call"
                  onClick={handleCallRequest}
                >
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
          </>
        )}
      </div>
    </div>
  );
};

export default CameraDetail;
