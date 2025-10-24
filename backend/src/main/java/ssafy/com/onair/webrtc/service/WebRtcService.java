package ssafy.com.onair.webrtc.service;

import io.livekit.server.*;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.sse.manager.SseManager;
import ssafy.com.onair.webrtc.config.LiveKitProperties;
import ssafy.com.onair.webrtc.dto.WebRtcRequestDto;

import java.util.concurrent.ConcurrentHashMap;

@RequiredArgsConstructor
@Service
public class WebRtcService {

    private final LiveKitProperties liveKitProperties;
    private final SseManager sseManager;

    public void requestConnection(WebRtcRequestDto webRtcRequestDto, CustomUserDetails senderDetails){

        String senderRole = senderDetails.getUserInfo().getRole();
        Long senderAccountId = senderDetails.getUserAccountId();
        Long receiverAccountId = null;

        // 사용자가 요청한거면 sender : 사용자, receiver : 관리자
        if(senderRole.equals("사용자")){
            // TODO: 관리자 AccountId 조회


        }
        // 관리자가 요청한거면 sender : 관리자, receiver : 사용자
        else if(senderRole.equals("관리자")){
            // 입력받은 receiverAccountId 사용
            receiverAccountId = webRtcRequestDto.receiverAccountId();
        }

        // TODO: receiver에게 sse로 요청 사실을 전달하기
        ConcurrentHashMap<Long, SseEmitter> sseEmitterMap = sseManager.getEmitters();
    }

    public void responseConnection(){

    }

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