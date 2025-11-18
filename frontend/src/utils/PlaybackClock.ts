export class PlaybackClock {
    private startTime = 0;
    private offset = 0;
    private running = false;
  
    start() {
      if (this.running) return;
      this.running = true;
      this.startTime = performance.now();
    }
  
    pause() {
      if (!this.running) return;
      this.offset = this.now();
      this.running = false;
    }
  
    now() {
      if (!this.running) return this.offset;
      return this.offset + (performance.now() - this.startTime);
    }
  }
  