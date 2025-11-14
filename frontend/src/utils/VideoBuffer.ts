/**
 * VideoBuffer - timeline 기반 비디오 재생 버퍼
 */

interface VideoFrame {
  timestamp: number;
  blobUrl: string;
}

interface VideoBufferConfig {
  maxBufferSize?: number;
  onFrameReady?: (blobUrl: string) => void;
  onBufferStatus?: (status: BufferStatus) => void;
}

interface BufferStatus {
  bufferLength: number;
  droppedFrames: number;
}

export class VideoBuffer {
  private buffer: VideoFrame[] = [];
  private playbackClock = 0;
  private maxBufferSize: number;
  private onFrameReady?: (blobUrl: string) => void;
  private onBufferStatus?: (status: BufferStatus) => void;

  private droppedFrames = 0;

  constructor(config: VideoBufferConfig = {}) {
    this.maxBufferSize = config.maxBufferSize ?? 20;
    this.onFrameReady = config.onFrameReady;
    this.onBufferStatus = config.onBufferStatus;
  }

  /** 클럭 업데이트 (timeline) */
  updateClock(time: number) {
    this.playbackClock = time;
    this.tryPlayback();
  }

  /** 버퍼에 비디오 프레임 추가 */
  enqueue(timestamp: number, frame: ArrayBuffer) {
    // 버퍼 오버플로우 방지
    if (this.buffer.length >= this.maxBufferSize) {
      const drop = this.buffer.shift();
      drop && URL.revokeObjectURL(drop.blobUrl);
      this.droppedFrames++;
    }

    const blob = new Blob([frame], { type: "image/jpeg" });
    const blobUrl = URL.createObjectURL(blob);

    this.buffer.push({ timestamp, blobUrl });
  }

  /** timeline 기준으로 프레임을 재생 */
  private tryPlayback() {
    if (this.buffer.length === 0) return;

    // timeline 이하에서 가장 최근 프레임 찾기
    let index = -1;
    for (let i = 0; i < this.buffer.length; i++) {
      if (this.buffer[i].timestamp <= this.playbackClock) {
        index = i;
      } else {
        break;
      }
    }

    if (index === -1) return;

    // 선택된 프레임까지 버퍼에서 제거
    const selectedFrame = this.buffer[index];

    for (let i = 0; i <= index; i++) {
      const f = this.buffer.shift();
      if (f && f !== selectedFrame) {
        URL.revokeObjectURL(f.blobUrl);
      }
    }

    // 재생
    if (this.onFrameReady) {
      this.onFrameReady(selectedFrame.blobUrl);
    }

    this.onBufferStatus?.({
      bufferLength: this.buffer.length,
      droppedFrames: this.droppedFrames,
    });
  }

  /** 메모리 정리 */
  clear() {
    this.buffer.forEach(f => URL.revokeObjectURL(f.blobUrl));
    this.buffer = [];
  }
}
