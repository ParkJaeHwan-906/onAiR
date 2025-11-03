package ssafy.com.onair.webrtc.controller;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.user.repository.UserAccountsRepository;
import ssafy.com.onair.webrtc.dto.WebRtcRequestDto;
import ssafy.com.onair.webrtc.dto.WebRtcResponseDto;
import ssafy.com.onair.webrtc.service.WebRtcService;

import java.time.LocalDateTime;
import java.util.Map;

@Slf4j
@RestController
@RequiredArgsConstructor
@RequestMapping("/webrtc")
public class WebRtcController {

    private final WebRtcService webRtcService;

    @PostMapping("/request")
    public ResponseEntity<?> request(
            @AuthenticationPrincipal CustomUserDetails senderDetails,
            @RequestBody WebRtcRequestDto webRtcRequestDto
    ){
        log.debug("requested sender info: {}", senderDetails);

        // 연결 요청 메서드
        webRtcService.requestConnection(webRtcRequestDto, senderDetails);

        // 응답
        return ResponseEntity
                .status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success(null));
    }

    @PostMapping("/response")
    public ResponseEntity<?> response(
            @AuthenticationPrincipal CustomUserDetails receiverDetails,
            @RequestBody WebRtcResponseDto webRtcResponseDto
    ){
        // 거절요청이라면 sender에 sse로 거절 사실 전달 -> return
        if(!webRtcResponseDto.acceptConnection()){
            // 거절 사실 전달
            webRtcService.responseConnection(webRtcResponseDto, receiverDetails, null);
            // 응답
            return ResponseEntity
                    .status(HttpStatus.ACCEPTED)
                    .body(ApiResponse.success(null)
                    );
        }
        // 토큰 생성하기
        String roomName = "room_" + LocalDateTime.now();
        String metadata = "metadata";   // TODO: 의미 있는 메타데이터로 바꾸기

        // 수신자 토큰
        String receiverAccessToken = webRtcService.createToken(
                receiverDetails.getUsername(),
                receiverDetails.getUserAccountId() + "",
                metadata,
                roomName
            );

        // 발신자 토큰
        String senderAccessToken = webRtcService.createToken(
                webRtcResponseDto.senderName(),
                webRtcResponseDto.senderAccountId() + "",
                metadata,
                roomName
            );

        // sender에 sse로 토큰 전달
        webRtcService.responseConnection(webRtcResponseDto, receiverDetails, senderAccessToken);

        // 응답(토큰 포함)
        return ResponseEntity
                .status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success(Map.of(
                        "accessToken", receiverAccessToken
                )));
    }



    @GetMapping("/create-token")
    public ResponseEntity<?> createToken(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestParam String roomName
    ){
        // 토큰 생성
        String webrtcToken = webRtcService.createToken(
                userDetails.getUsername(),
                userDetails.getUserAccountId() + "",
                "metadata", // TODO: 의미 있는 메타데이터로 바꾸기
                roomName
        );

        // 작업자에게 토큰 보내주기
        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(ApiResponse.success(webrtcToken));
    }
}