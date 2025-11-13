// public/audio-processor.js
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    const outRate = sampleRate; // Worklet 전역 (브라우저 AudioContext.sampleRate)
    // 버퍼 및 인덱스 초기화
    this.bufferSize = Math.max(32768, Math.floor(outRate * 2)); // 최소 32k, 최대 약 2초 분량
    this.buffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.readIndex = 0;
    this.availableSamples = 0;

    // 재생 시작 임계치: 약 0.2초 (초반 지연 너무 크지 않게)
    this.minBufferThreshold = Math.floor(outRate * 0.2);

    // 최대 허용 지연(초) — 이보다 쌓이면 강제 클리어
    this.maxLatencySec = 0.6;
    this.maxLatencySamples = Math.floor(outRate * this.maxLatencySec);

    this.started = false;
    this.lastSample = 0.0;

    // 메인 스레드로부터 메시지 수신
    this.port.onmessage = (event) => {
      if (event.data && event.data.type === "audio_frame") {
        // event.data.frame 은 Float32Array로 온다고 가정
        this.enqueue(event.data.frame);
      } else if (event.data && event.data.type === "clear") {
        // 필요 시 외부에서 전체 버퍼 클리어 요청 가능
        this.readIndex = this.writeIndex;
        this.availableSamples = 0;
        this.started = false;
      }
    };
  }

  // 업샘플링(입력 16k -> output sampleRate) 및 버퍼 적재
  enqueue(frame) {
    if (!frame || frame.length === 0) return;

    const inputRate = 16000; // 라즈베리파이 / 테스트 송신 기본값
    const outputRate = sampleRate; // Worklet의 재생 샘플레이트
    const ratio = outputRate / inputRate;

    // 업샘플링 후 예상길이
    const destLen = Math.max(1, Math.floor(frame.length * ratio));

    // 만약 이미 너무 많은 샘플이 쌓였다면(지연 초과) → 강제 클리어
    if (this.availableSamples > this.maxLatencySamples) {
      // 오래된 버퍼 전부 제거 (에코/중첩 방지)
      this.readIndex = this.writeIndex;
      this.availableSamples = 0;
      this.started = false;
      // 계속 진행해 새로운 데이터는 받아서 재생 시작 조건 다시 채움
    }

    // 버퍼 여유 확인, 부족하면 오래된 데이터 일부 제거
    const freeSpace = this.bufferSize - this.availableSamples;
    if (destLen > freeSpace) {
      const overflow = destLen - freeSpace;
      // 간단하게 오래된 것을 버림 (readIndex 앞으로 이동)
      this.readIndex = (this.readIndex + overflow) % this.bufferSize;
      this.availableSamples = Math.max(0, this.availableSamples - overflow);
    }

    // 업샘플링: fractional resampling (linear interpolation)
    // destLen = floor(frame.length * ratio)
    let writePos = this.writeIndex;
    const srcLen = frame.length;
    for (let d = 0; d < destLen; d++) {
      // source position in float
      const srcPos = d / ratio;
      const i = Math.floor(srcPos);
      const frac = srcPos - i;
      const s0 = frame[i] ?? frame[srcLen - 1];
      const s1 = (i + 1 < srcLen) ? frame[i + 1] : s0;
      const val = s0 * (1 - frac) + s1 * frac;
      this.buffer[writePos] = val;
      writePos = (writePos + 1) % this.bufferSize;
    }

    // 인덱스/가용 샘플 갱신
    this.writeIndex = writePos % this.bufferSize;
    this.availableSamples = Math.min(this.bufferSize, this.availableSamples + destLen);
  }

  // 출력 버퍼에 샘플 채워넣기
  dequeue(output) {
    const outLen = output.length;
    if (this.availableSamples < outLen) {
      // 부족하면 직전 샘플을 점차 감쇠시키며 채움(갑작스런 클릭/노이즈 완화)
      for (let i = 0; i < outLen; i++) {
        this.lastSample *= 0.93;
        output[i] = this.lastSample;
      }
      return;
    }

    // 정상적으로 읽어서 채우기
    let idx = this.readIndex;
    for (let i = 0; i < outLen; i++) {
      output[i] = this.buffer[idx];
      this.lastSample = output[i];
      idx = (idx + 1) % this.bufferSize;
    }
    this.readIndex = idx;
    this.availableSamples -= outLen;
  }

  process(inputs, outputs) {
    const output = outputs[0][0]; // 단일 채널

    // 재생 시작 조건: 최소 버퍼 확보
    if (!this.started) {
      if (this.availableSamples >= this.minBufferThreshold) {
        this.started = true;
      } else {
        // 아직 시작할 만큼 쌓이지 않음 → 무음 출력
        output.fill(0);
        return true;
      }
    }

    // 만약 버퍼가 지나치게 밀려있으면(지연 심함) → 오래된 것 전부 팝하여 리-싱크
    if (this.availableSamples > this.maxLatencySamples) {
      // 강제 리셋: 중첩/에코 방지
      this.readIndex = this.writeIndex;
      this.availableSamples = 0;
      this.started = false;
      output.fill(0);
      return true;
    }

    // 평상시: dequeue로 채움
    this.dequeue(output);
    return true;
  }
}

registerProcessor("audio-processor", AudioProcessor);
