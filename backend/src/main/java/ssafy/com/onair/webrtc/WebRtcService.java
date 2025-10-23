package ssafy.com.onair.webrtc;

import io.livekit.server.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class WebRtcService {

    private final String apiKey;
    private final String secretKey;

    public WebRtcService(@Value("${livekit.api.key}") String apiKey,
                         @Value("${livekit.api.secret}") String secretKey) {
        this.apiKey = apiKey;
        this.secretKey = secretKey;
    }

    public String createToken(String participantName, String participantId, String metadata, String roomName) {
        AccessToken token = new AccessToken(apiKey, secretKey);
        token.setName(participantName);
        token.setIdentity(participantId);
        token.setMetadata(metadata);
        token.addGrants(new RoomJoin(true), new RoomName(roomName));

        return token.toJwt();
    }
}