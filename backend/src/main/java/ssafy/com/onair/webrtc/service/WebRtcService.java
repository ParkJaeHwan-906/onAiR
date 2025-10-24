package ssafy.com.onair.webrtc.service;

import io.livekit.server.*;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import ssafy.com.onair.sse.manager.SseManager;
import ssafy.com.onair.webrtc.config.LiveKitProperties;

@RequiredArgsConstructor
@Service
public class WebRtcService {

    private final LiveKitProperties liveKitProperties;
    private final SseManager sseManager;

    public String createToken(String participantName, String participantId, String metadata, String roomName) {
        String apiKey = liveKitProperties.key();
        String secretKey = liveKitProperties.secret();

        AccessToken token = new AccessToken(apiKey, secretKey);
        token.setName(participantName);
        token.setIdentity(participantId);
        token.setMetadata(metadata);
        token.addGrants(new RoomJoin(true), new RoomName(roomName));

        return token.toJwt();
    }
}