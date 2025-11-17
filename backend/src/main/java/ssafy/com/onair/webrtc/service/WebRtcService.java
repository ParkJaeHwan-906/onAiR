package ssafy.com.onair.webrtc.service;


import io.livekit.server.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.sse.manager.SseManager;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.webrtc.config.LiveKitProperties;
import ssafy.com.onair.webrtc.dto.SenderInfoDto;
import ssafy.com.onair.webrtc.dto.SseResponseDto;
import ssafy.com.onair.webrtc.dto.WebRtcRequestDto;
import ssafy.com.onair.webrtc.dto.WebRtcResponseDto;
import ssafy.com.onair.webrtc.manager.WebRtcManager;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@RequiredArgsConstructor
@Service
public class WebRtcService {

    private final LiveKitProperties liveKitProperties;
    private final WebRtcManager webRtcManager;
    private final SseManager sseManager;

    public void requestConnection(WebRtcRequestDto webRtcRequestDto, CustomUserDetails senderDetails){

        UserInfoDto senderInfo = senderDetails.getUserInfo();
        SenderInfoDto senderInfoDto = SenderInfoDto.builder()
                .senderAccountId(senderInfo.getUserAccountId())
                .companyId(senderInfo.getCompanyId())
                .name(senderInfo.getName())
                .phone(senderInfo.getPhone())
                .role(senderInfo.getRole())
                .equipmentId(senderInfo.getEquipmentId())
                .equipmentName(senderInfo.getEquipmentName())
                .equipmentCategoryId(senderInfo.getEquipmentCategoryId())
                .equipmentCategoryName(senderInfo.getEquipmentCategoryName())
                .description(webRtcRequestDto.description())    // TODO: AI 서포터 질문 요약 추가하기
                .build();
        String senderRole = senderInfo.getRole();

        log.debug("webrtc senderInfo : {}", senderInfo);

        StringBuilder roomName = new StringBuilder();
        roomName.append(senderInfoDto.senderAccountId()).append(' ').append(webRtcRequestDto.receiverAccountId());
        webRtcManager.getWaitingRoomList().put(roomName.toString(), LocalDateTime.now().plusMinutes(1));
        // 사용자가 요청한거면 sender : 사용자, receiver : 관리자
        if(senderRole.equals("사용자")){
            // 작업자 -> 관리자
            sseManager.sendRequestWorkerToAdmin(senderInfo.getCompanyId(), senderInfoDto, "callRequest");
        }
        // 관리자가 요청한거면 sender : 관리자, receiver : 사용자
        else if(senderRole.equals("관리자")){
            // 관리자 -> 작업자
            sseManager.sendRequestAdminToWorker(webRtcRequestDto.receiverAccountId(), senderInfoDto, "callRequest");
        }
    }

    public void responseConnection(WebRtcResponseDto webRtcResponseDto, CustomUserDetails receiverDetails, String senderAccessToken){
        UserInfoDto receiverInfo = receiverDetails.getUserInfo();

        SseResponseDto responseDto = SseResponseDto.builder()
                .acceptConnection(webRtcResponseDto.acceptConnection())
                .accessToken(senderAccessToken)
                .build();

        if(receiverInfo.getRole().equals("사용자")){
            // 작업자 -> 관리자
            sseManager.sendRequestWorkerToAdmin(receiverInfo.getCompanyId(), responseDto, "callResponse");
        }
        else if(receiverInfo.getRole().equals("관리자")){
            // 관리자 -> 작업자
            sseManager.sendRequestAdminToWorker(webRtcResponseDto.senderAccountId(), responseDto, "callResponse");
        }

        // 대기 중인 방 리스트에서 제거
        StringBuilder roomName = new StringBuilder();
        roomName.append(webRtcResponseDto.senderAccountId()).append(' ').append(receiverInfo.getUserAccountId());
        try{
            webRtcManager.getWaitingRoomList().remove(roomName.toString());
        }catch (Exception e){
            log.error(e.getMessage());
        }
    }

    public String createToken(String participantName, String participantId, String metadata, String roomName) {
        String apiKey = liveKitProperties.key();
        String secretKey = liveKitProperties.secret();

        AccessToken token = new AccessToken(apiKey, secretKey);
        token.setName(participantName);
        token.setIdentity(participantId);
        token.setMetadata(metadata);
        token.addGrants(new RoomJoin(true), new RoomName(roomName));

        // 액세스 토큰 만료 시간 
        // TODO: 지금은 테스트로 1주일로 잡았고, 나중에 적절히 수정할 것
        token.setTtl(7 * 24 * 60 * 60 * 1000);

        return token.toJwt();
    }
}