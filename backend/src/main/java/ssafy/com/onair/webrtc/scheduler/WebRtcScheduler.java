package ssafy.com.onair.webrtc.scheduler;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import ssafy.com.onair.sse.manager.SseManager;
import ssafy.com.onair.webrtc.manager.WebRtcManager;

import java.time.LocalDateTime;
import java.util.StringTokenizer;

@Slf4j
@Component
@RequiredArgsConstructor
public class WebRtcScheduler {
    private final WebRtcManager webRtcManager;
    private final SseManager sseManager;

//    @Scheduled(fixedRate = 1000 * 60 * 5)
    @Scheduled(fixedRate = 1000 * 20)
    public void removeTimeOutRooms() {
        if(webRtcManager.getWaitingRoomList().isEmpty()) return;

        String[] roomNameList = webRtcManager.getWaitingRoomList().keySet().toArray(new String[0]);
        for(String roomName : roomNameList) {
            if(webRtcManager.getWaitingRoomList().get(roomName).isAfter(LocalDateTime.now())) {
                webRtcManager.getWaitingRoomList().remove(roomName);
                StringTokenizer st = new StringTokenizer(roomName);
                Long senderAccountId = Long.parseLong(st.nextToken());
                Long receiverAccountId = Long.parseLong(st.nextToken());
                sseManager.sendRtcCancelEvent(senderAccountId, receiverAccountId);
                log.info("{} room was closed", roomName);
            }
        }
    }
}
