package ssafy.com.onair.webrtc.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.webrtc.service.WebRtcService;


@RestController
@RequiredArgsConstructor
@RequestMapping("/webrtc")
public class WebRtcController {

    private final WebRtcService webRtcService;

    @GetMapping("/create-token")
    public ResponseEntity<?> createToken(
            @AuthenticationPrincipal CustomUserDetails userDetails
    ){

        // TODO: 여러 작업자의 요청 대응하기

        // 토큰 생성
        String webrtcToken = webRtcService.createToken(
                userDetails.getUsername(),
                userDetails.getUserAccountId() + "",
                "metadata", // TODO: 의미 있는 메타데이터로 바꾸기
                "room_" + userDetails.getUsername() + "_" + userDetails.getUserAccountId()
        );

        // TODO: SSE로 관제실 서버에 먼저 토큰 보내주기


        // 작업자에게 토큰 보내주기
        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(ApiResponse.success(webrtcToken));
    }
}