/**
 * 비디오 프레임 버퍼링 클래스
 * 오디오 프로세서와 유사한 버퍼링 메커니즘을 비디오에 적용
 */

interface VideoFrame {
  timestamp: number;
  frame: ArrayBuffer;
  blobUrl?: string; // Blob URL 캐싱용
}

interface VideoBufferConfig {
  minBufferSize?: number;      // 최소 버퍼 크기 (프레임 수)
  targetBufferSize?: number;   // 목표 버퍼 크기
  maxBufferSize?: number;      // 최대 버퍼 크기
  targetFPS?: number;          // 목표 FPS
  onFrameReady?: (blobUrl: string) => void; // 프레임 준비 완료 콜백
  onBufferStatus?: (status: BufferStatus) => void; // 버퍼 상태 변경 콜백
}

interface BufferStatus {
  isPlaying: boolean;
  bufferLength: number;
  droppedFrames: number;
  currentFPS: number;
}

export class VideoBuffer {
  private buffer: VideoFrame[] = [];
  private isPlaying: boolean = false;
  private animationFrameId: number | null = null;
  
  // 설정값
  private minBufferSize: number;
  private targetBufferSize: number;
  private maxBufferSize: number;
  private targetFPS: number;
  private frameInterval: number; // ms 단위
  
  // 콜백
  private onFrameReady?: (blobUrl: string) => void;
  private onBufferStatus?: (status: BufferStatus) => void;
  
  // 통계
  private droppedFrames: number = 0;
  private lastFrameTime: number = 0;
  private currentFPS: number = 0;
  private fpsCounter: number = 0;
  private fpsLastCheck: number = 0;

  constructor(config: VideoBufferConfig = {}) {
    this.minBufferSize = config.minBufferSize ?? 3;      // 최소 3프레임 확보
    this.targetBufferSize = config.targetBufferSize ?? 5; // 목표 5프레임
    this.maxBufferSize = config.maxBufferSize ?? 10;      // 최대 10프레임
    this.targetFPS = config.targetFPS ?? 30;              // 30fps
    this.frameInterval = 1000 / this.targetFPS;
    
    this.onFrameReady = config.onFrameReady;
    this.onBufferStatus = config.onBufferStatus;
    
    console.log(`[VideoBuffer] 초기화 완료 - 최소: ${this.minBufferSize}, 목표: ${this.targetBufferSize}, 최대: ${this.maxBufferSize} 프레임`);
  }

  /**
   * 프레임을 버퍼에 추가
   */
  enqueue(timestamp: number, frame: ArrayBuffer): void {
    // 버퍼 오버플로우 방지
    if (this.buffer.length >= this.maxBufferSize) {
      // 가장 오래된 프레임들 제거
      const dropCount = Math.floor((this.buffer.length - this.targetBufferSize) / 2);
      for (let i = 0; i < dropCount; i++) {
        const dropped = this.buffer.shift();
        if (dropped?.blobUrl) {
          URL.revokeObjectURL(dropped.blobUrl);
        }
      }
      this.droppedFrames += dropCount;
      console.warn(`[VideoBuffer] 버퍼 오버플로우! ${dropCount}개 프레임 드롭`);
    }

    // Blob URL 미리 생성 (나중에 메인스레드에서 생성하면 느림)
    const blob = new Blob([frame], { type: "image/jpeg" });
    const blobUrl = URL.createObjectURL(blob);

    this.buffer.push({
      timestamp,
      frame,
      blobUrl
    });

    // 버퍼가 충분히 쌓이면 재생 시작
    if (!this.isPlaying && this.buffer.length >= this.minBufferSize) {
      console.log(`✅ [VideoBuffer] 버퍼링 완료! 재생 시작 (${this.buffer.length}개 프레임)`);
      this.start();
    }
  }

  /**
   * 버퍼에서 프레임을 꺼냄
   */
  private dequeue(): VideoFrame | null {
    if (this.buffer.length === 0) {
      return null;
    }
    return this.buffer.shift() ?? null;
  }

  /**
   * 재생 시작
   */
  start(): void {
    if (this.isPlaying) {
      return;
    }

    this.isPlaying = true;
    this.lastFrameTime = performance.now();
    this.fpsLastCheck = this.lastFrameTime;
    this.fpsCounter = 0;
    
    this.playbackLoop();
  }

  /**
   * 재생 중단
   */
  stop(): void {
    this.isPlaying = false;
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    console.log(`[VideoBuffer] 재생 중단`);
  }

  /**
   * 재생 루프 (requestAnimationFrame 기반)
   */
  private playbackLoop = (): void => {
    if (!this.isPlaying) {
      return;
    }

    const now = performance.now();
    const elapsed = now - this.lastFrameTime;

    // 버퍼가 비었으면 재버퍼링
    if (this.buffer.length === 0) {
      console.warn(`⚠️ [VideoBuffer] 버퍼가 비었습니다. 재버퍼링 대기 중...`);
      this.isPlaying = false;
      this.emitBufferStatus();
      return;
    }

    // 프레임 간격이 되면 다음 프레임 재생
    if (elapsed >= this.frameInterval) {
      const frame = this.dequeue();
      
      if (frame && frame.blobUrl) {
        // 콜백으로 프레임 전달
        if (this.onFrameReady) {
          this.onFrameReady(frame.blobUrl);
        }

        this.lastFrameTime = now;
        this.fpsCounter++;

        // FPS 계산 (1초마다)
        if (now - this.fpsLastCheck >= 1000) {
          this.currentFPS = this.fpsCounter;
          this.fpsCounter = 0;
          this.fpsLastCheck = now;
          
          // 버퍼 상태 알림
          this.emitBufferStatus();
        }
      }
    }

    // 다음 프레임 스케줄링
    this.animationFrameId = requestAnimationFrame(this.playbackLoop);
  };

  /**
   * 버퍼 상태 알림
   */
  private emitBufferStatus(): void {
    if (this.onBufferStatus) {
      this.onBufferStatus({
        isPlaying: this.isPlaying,
        bufferLength: this.buffer.length,
        droppedFrames: this.droppedFrames,
        currentFPS: this.currentFPS
      });
    }
  }

  /**
   * 버퍼 정리 (메모리 누수 방지)
   */
  clear(): void {
    this.stop();
    
    // 모든 Blob URL 정리
    for (const frame of this.buffer) {
      if (frame.blobUrl) {
        URL.revokeObjectURL(frame.blobUrl);
      }
    }
    
    this.buffer = [];
    this.droppedFrames = 0;
    this.currentFPS = 0;
    this.fpsCounter = 0;
    
    console.log(`[VideoBuffer] 버퍼 정리 완료`);
  }

  /**
   * 현재 버퍼 상태 조회
   */
  getStatus(): BufferStatus {
    return {
      isPlaying: this.isPlaying,
      bufferLength: this.buffer.length,
      droppedFrames: this.droppedFrames,
      currentFPS: this.currentFPS
    };
  }
}

