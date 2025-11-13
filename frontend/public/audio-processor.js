// public/audio-processor.js
class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
      super();


      // 버퍼 : 약 1초 분량 저장
      this.bufferSize = 32000; // 16kHz 기준 1초
      this.buffer = new Float32Array(this.bufferSize);
      this.writeIndex = 0;
      this.readIndex = 0;
      this.availableSamples = 0;
      this.started = false;
      this.minBufferThreshold = 16000; // 1초 버퍼 확보 후 재생 시작 
      this.lastSample = 0; // 마지막 출력 샘플 저장
      
      // 메인 스레드로부터 메시지 수신
      this.port.onmessage = (event) => {
        if (event.data && event.data.type === "audio_frame") {
          this.enqueue(event.data.frame);
        }
      };
    }

    enqueue(frame){
      for (let i = 0; i < frame.length; i++) {
        this.buffer[this.writeIndex] = frame[i];
        this.writeIndex = (this.writeIndex + 1) % this.bufferSize;
      }
      this.availableSamples = Math.min(this.availableSamples + frame.length, this.bufferSize);
    }

    dequeue(output) {
      if (this.availableSamples < output.length) {
        // 데이터 부족 → 부족 시 직전 샘플로 채움 (보간)
        // 부드러운 감쇠 보간
        for (let i = 0; i < output.length; i++) {
          this.lastSample *= 0.95;
          output[i] = this.lastSample;
        }
        return;
      }
  
      for (let i = 0; i < output.length; i++) {
        output[i] = this.buffer[this.readIndex];
        this.lastSample = output[i]; // ✅ 직전 샘플 갱신
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
      this.availableSamples -= output.length;
    }
  
    process(inputs, outputs) {
      const output = outputs[0][0]; // 단일 채널 기준
  
      // 최소 버퍼 확보 전까지는 재생 안 함
      if (!this.started) {
        if (this.availableSamples > this.minBufferThreshold) {
          this.started = true;
        } else {
          output.fill(0);
          return true;
        }
      }

      // 버퍼에서 일정량 dequeue
      this.dequeue(output);
      return true;
    }
  }
  
  registerProcessor("audio-processor", AudioProcessor);
  