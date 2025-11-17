import React, { useEffect, useRef, useState } from "react";
import type { CCTVItem } from "../../types/cctv";
import { PhoneCall, Headphones, Mic } from "lucide-react";

// 소켓 연결 훅 (이미 프로젝트에 있음)
import { useSocket } from "../../utils/socketContext";

// Backdoor 영상 처리를 위해 사용했던 유틸리티
import { VideoBuffer } from "../../utils/VideoBuffer";
import { PlaybackClock } from "../../utils/PlaybackClock";

import "../../styles/CCTV.css";

interface CameraDetailProps {
  camera: CCTVItem; // 카메라 정보
  onClose: () => void; // 닫기 버튼
}

/*
=====================================================
  CameraDetail
  - CCTV 상세 화면
  - 'isLive' 값이 true면 실제 소켓 기반 라이브 스트림 사용
  - false면 기존에 쓰던 더미 영상 재생
=====================================================
*/
const CameraDetail: React.FC<CameraDetailProps> = ({ camera, onClose }) => {
  // 🔌 현재 연결된 socket 객체 가져오기
  const socket = useSocket();

  // IMG 태그 DOM을 직접 조작하기 위한 ref
  const imgRef = useRef<HTMLImageElement>(null);

  // 수신된 영상 프레임을 저장하는 버퍼
  const videoBufferRef = useRef<VideoBuffer | null>(null);

  // 비디오 프레임 재생 타이밍을 맞추기 위한 clock
  const clockRef = useRef<PlaybackClock | null>(null);

  // “라이브 스트림이 정상적으로 수신되기 시작했는지" 체크용
  const [isLiveConnected, setIsLiveConnected] = useState(false);

  /* 
  =====================================================
  실시간 비디오 스트림 이벤트 처리
  - BackdoorPage에서 사용한 VideoBuffer 그대로 사용
  - 'video_frame' 이벤트 받을 때마다 버퍼에 축적
  - 버퍼는 프레임 순서와 시간 기준으로 재생 관리함
  =====================================================
  */
  useEffect(() => {
    // 라이브 스트림 아니면 실행 X
    if (!socket || !camera.isLive) return;

    // 비디오 버퍼 생성
    const videoBuffer = new VideoBuffer({
      maxBufferSize: 12, // 프레임 최대 12개 저장
      onFrameReady: (blobUrl: string) => {
        // 준비된 최신 프레임을 IMG 태그로 보여줌
        if (imgRef.current) {
          // 이전 blob URL 정리 (메모리 누수 방지)
          if (imgRef.current.src.startsWith("blob:")) {
            URL.revokeObjectURL(imgRef.current.src);
          }

          imgRef.current.src = blobUrl;
        }
      },
    });

    videoBufferRef.current = videoBuffer;

    // 서버에서 보내주는 실시간 프레임 수신
    const handleVideoFrame = (data: {
      timestamp: number;
      frame: ArrayBuffer;
    }) => {
      // 버퍼에 프레임 넣기
      videoBuffer.enqueue(data.timestamp, data.frame);

      // 첫 프레임이 들어오면 “연결됨”
      if (!isLiveConnected) setIsLiveConnected(true);
    };

    socket.on("video_frame", handleVideoFrame);

    // cleanup
    const currentImgRef = imgRef.current;
    return () => {
      // socket.off("video_frame", handleVideoFrame);

      videoBuffer.clear();

      // UI 이미지에 사용된 blob URL 제거
      if (currentImgRef && currentImgRef.src.startsWith("blob:")) {
        URL.revokeObjectURL(currentImgRef.src);
      }
    };
  }, [socket, camera.isLive]);

  /*
  =====================================================
  비디오 재생 clock 설정
  - 영상 프레임을 timestamp 기준으로 재생하려면
  기준 clock이 필요함 (안 그러면 프레임이 튀거나 어긋남)
  - 60fps 기준으로 부드럽게 업데이트
  =====================================================
  */
  useEffect(() => {
    if (!camera.isLive) return;

    // clock 생성
    const clock = new PlaybackClock();
    clock.start();
    clockRef.current = clock;

    // 약 60fps로 clock 전달
    const interval = setInterval(() => {
      const now = clock.now();

      if (videoBufferRef.current) {
        videoBufferRef.current.updateClock(now);
      }
    }, 16);

    return () => clearInterval(interval);
  }, [camera.isLive]);

  /*
  =====================================================
  렌더링 부분
  - camera.isLive === true → 라이브 스트림 IMG로 렌더링
  - false → 기존 더미 영상 video 태그로 렌더링
  =====================================================
  */
  return (
    <div className="detail-view">
      {/* 닫기 버튼 */}
      <button className="detail-close-inline" onClick={onClose}>
        ✕
      </button>

      <div className="detail-video-box">
        {camera.isLive ? (
          // 라이브 모드: 실시간 스트림
          <img
            ref={imgRef}
            alt="Live Stream"
            className="detail-video-inline"
            style={{ display: "block" }}
          />
        ) : (
          // 기존 더미 영상 모드
          <video
            src={camera.videoUrl}
            autoPlay
            muted
            loop
            playsInline
            className="detail-video-inline"
          />
        )}

        {/* 좌하단 라벨 + 컨트롤 버튼 */}
        <div className="detail-info-inline">
          <div className="detail-label-inline">
            {camera.worker.name} | {camera.equipment.name}
          </div>

          <div className="detail-inline-buttons">
            <button className="detail-ctrl-btn call">
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
      </div>
    </div>
  );
};

export default CameraDetail;
