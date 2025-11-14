class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    this.bufferSize = 100000;
    this.buffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.readIndex = 0;
    this.availableSamples = 0;
    this.started = false;

    this.minBufferThreshold = 45000;  // 최소 버퍼 확보 (1초 정도)
    this.targetBuffer = 50000;        // 목표 버퍼 수위
    this.maxBufferThreshold = 70000;  // 너무 많으면 프레임 일부 버림

    this.lastSample = 0;
    this.slowdownFactor = 1.0;        // 재생속도 보정용 (1.0 = 정상)
    this.adjustRate = 0.0001;         // 보정 속도 (너무 크면 끊김)

    this.port.onmessage = (event) => {
      if (!event.data) return;
    
      if (event.data.type === "audio_frame") {
        this.enqueue(event.data.frame);
      } else if (event.data.type === "clock") {
        this.syncClock(event.data.time);
      }
    };
    
  }
  syncClock(clockTime) {
    // clockTime은 ms 단위라고 가정
    const bufferTime = (this.availableSamples / sampleRate) * 1000; // ms 단위
    const targetTime = clockTime; // timeline 기준
    const audioTime = this.readIndex / sampleRate * 1000; 
  
    const drift = audioTime - targetTime; // +: 오디오 느림, -: 오디오 빠름
    this.slowdownFactor = 1 - drift * 0.00005; // 조절 계수는 실험 필요
    this.slowdownFactor = Math.max(0.97, Math.min(1.03, this.slowdownFactor));
  }

  enqueue(frame) {
    const inputRate = 16000;
    const outputRate = sampleRate;
    const ratio = outputRate / inputRate;

    let outPos = this.writeIndex;

    for (let i = 0; i < frame.length - 1; i++) {
      const start = frame[i];
      const end = frame[i + 1];
      for (let j = 0; j < Math.floor(ratio); j++) {
        const alpha = j / ratio;
        this.buffer[outPos % this.bufferSize] = start * (1 - alpha) + end * alpha;
        outPos++;
      }
    }

    this.buffer[outPos % this.bufferSize] = frame[frame.length - 1];
    outPos++;

    this.writeIndex = outPos % this.bufferSize;
    this.availableSamples = Math.min(this.availableSamples + Math.floor(frame.length * ratio), this.bufferSize);

    // 버퍼 과잉 시 일부 프레임 버림 (급격한 지연 방지)
    if (this.availableSamples > this.maxBufferThreshold) {
      const skip = Math.floor((this.availableSamples - this.targetBuffer) / 2);
      this.readIndex = (this.readIndex + skip) % this.bufferSize;
      this.availableSamples -= skip;
      console.warn(`[AudioProcessor] Dropped ${skip} samples (buffer too full)`);
    }
  }

  dequeue(output) {
    if (this.availableSamples < output.length) {
      for (let i = 0; i < output.length; i++) {
        this.lastSample *= 0.95;
        output[i] = this.lastSample;
      }
      return;
    }

    // ✅ 드리프트 제어: 버퍼 상태에 따라 속도 보정
    const bufferDiff = this.availableSamples - this.targetBuffer;
    this.slowdownFactor -= bufferDiff * this.adjustRate; 
    this.slowdownFactor = Math.max(0.98, Math.min(1.02, this.slowdownFactor));

    for (let i = 0; i < output.length; i++) {
      const adjustedIndex = Math.floor(this.readIndex);
      output[i] = this.buffer[adjustedIndex % this.bufferSize];
      this.lastSample = output[i];
      this.readIndex += this.slowdownFactor;
      if (this.readIndex >= this.bufferSize) this.readIndex -= this.bufferSize;
    }

    this.availableSamples -= Math.floor(output.length * this.slowdownFactor);
  }

  process(inputs, outputs) {
    const output = outputs[0][0];
    if (!this.started) {
      if (this.availableSamples > this.minBufferThreshold) this.started = true;
      else {
        output.fill(0);
        return true;
      }
    }
    this.dequeue(output);
    return true;
  }
}

registerProcessor("audio-processor", AudioProcessor);
