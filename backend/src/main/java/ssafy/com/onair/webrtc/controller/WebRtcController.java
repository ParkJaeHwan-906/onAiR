package ssafy.com.onair.webrtc.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.webrtc.dto.WebRtcRequestDto;
import ssafy.com.onair.webrtc.dto.WebRtcResponseDto;
import ssafy.com.onair.webrtc.service.WebRtcService;


@RestController
@RequiredArgsConstructor
@RequestMapping("/webrtc")
public class WebRtcController {

    private final WebRtcService webRtcService;



    @PostMapping("/request")
    public ResponseEntity<?> request(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody WebRtcRequestDto webRtcRequestDto
    ){

        // 연결 요청 메서드
        webRtcService.requestConnection(webRtcRequestDto, userDetails);

        // 응답
        return ResponseEntity
                .status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success(null));
    }

    @PostMapping("/response")
    public ResponseEntity<?> response(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody WebRtcResponseDto webRtcResponseDto
    ){

        // TODO: 거절요청이라면 sender에 sse로 거절 사실 전달 -> return

        // TODO: 토큰 생성하기

        // TODO: sender에 sse로 토큰 전달



        // TODO: 응답(토큰 포함)
        return ResponseEntity
                .status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success(null));
    }



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