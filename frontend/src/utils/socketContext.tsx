import React, { createContext, useContext, useEffect, type ReactNode } from 'react';
import { io, type Socket } from 'socket.io-client';

// 1. 서버 주소 (FastAPI 서버 주소로 변경하세요)
const SOCKET_URL = 'http://localhost:8000'; // 예: "http://127.0.0.1:8000" 또는 실제 배포 주소

// --- 타입 정의 ---
// 서버 -> 클라이언트로 보내는 이벤트 (리스너: socket.on)
// 서버의 socket_manager.py를 기반으로 정의
interface ServerToClientEvents {
  server_message: (data: { msg: string }) => void;
  pong: (data: { msg: string }) => void;
  video_frame: (data: { frame: string }) => void;
  audio_frame: (data: { frame: string }) => void;
  'marker-created': (data: { msg: string }) => void;
}

// 클라이언트 -> 서버로 보내는 이벤트 (발신: socket.emit)
interface ClientToServerEvents {
  register_device: (data: { device: 'pc' | 'mobile' | 'raspi' }) => void;
  ping: (data: { data: string }) => void;
  video_stream: (data: { state: 'on' | 'off' }) => void;
  'video-frame': (data: { frame: string }) => void;
  'audio-frame': (data: { frame: string }) => void;
  'ar-marker': (data: { marker_x: number; marker_y: number }) => void;
}
// --- 타입 정의 끝 ---

// 2. 타입이 적용된 소켓 인스턴스 생성
const socket: Socket<ServerToClientEvents, ClientToServerEvents> = io(
  SOCKET_URL,
  {
    path: '/ws',
    autoConnect: false,
    transports: ['websocket'], // Polling 방식 말고 WebSocket을 우선적으로 사용
  }
);

// 3. 타입이 적용된 Socket Context 생성
const SocketContext =
  createContext<Socket<ServerToClientEvents, ClientToServerEvents>>(socket);

/**
 * 어떤 컴포넌트에서든 타입이 적용된 소켓 인스턴스에 접근할 수 있게 해주는 Custom Hook
 */
export const useSocket = () => {
  return useContext(SocketContext);
};

// Provider 컴포넌트의 Props 타입 정의
interface SocketProviderProps {
  children: ReactNode;
}

/**
 * 앱의 최상단(App.js)을 감싸줄 Provider 컴포넌트
 */
export const SocketProvider: React.FC<SocketProviderProps> = ({ children }) => {
  useEffect(() => {
    // 4. 컴포넌트 마운트 시 소켓 연결 (이후에는 로그인 이후에 연결하는 것으로 수정하기!)
    socket.connect();

    // 5. 서버 코드에 맞춘 'register_device' 이벤트 전송
    socket.on('connect', () => {
      console.log('Socket Connected:', socket.id);
      // (타입 추론됨) socket.emit('register_device', ...)
      socket.emit('register_device', { device: 'pc' });
    });

    // 연결 해제/오류 이벤트
    socket.on('disconnect', (reason) => {
      console.log('Socket Disconnected:', reason);
    });

    socket.on('connect_error', (err) => {
      console.error('Socket Connection Error:', err.message);
    });

    // 6. 컴포넌트 언마운트 시 소켓 연결 해제
    return () => {
      socket.disconnect();
      // 등록했던 이벤트 리스너들도 정리
      socket.off('connect');
      socket.off('server_message');
      socket.off('disconnect');
      socket.off('connect_error');
    };
  }, []); // 빈 배열: 앱이 시작될 때 단 한 번만 실행

  // 7. Context Provider를 통해 소켓 인스턴스를 하위 컴포넌트에 제공
  return (
    <SocketContext.Provider value={socket}>{children}</SocketContext.Provider>
  );
};