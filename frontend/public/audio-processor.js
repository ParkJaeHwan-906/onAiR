// public/audio-processor.js
class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
      super();
      this.queue = [];
      
      // 메인 스레드로부터 메시지 수신
      this.port.onmessage = (event) => {
        if (event.data && event.data.type === "audio_frame") {
          this.queue.push(event.data.frame);
        }
      };
    }
  
    process(inputs, outputs) {
      const output = outputs[0][0]; // 단일 채널 기준
  
      if (this.queue.length > 0) {
        const frame = this.queue.shift();
        output.set(frame.subarray(0, output.length));
      } else {
        output.fill(0);
      }
  
      // 계속 처리
      return true;
    }
  }
  
  registerProcessor("audio-processor", AudioProcessor);
  