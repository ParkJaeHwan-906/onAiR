package ssafy.com.onair.sse.controller;


import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.sse.manager.SseManager;

@RestController
@RequestMapping("/sse")
@RequiredArgsConstructor
public class SseController {

    private final SseManager sseManager;

    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter connectSse(@AuthenticationPrincipal CustomUserDetails user) {
        return sseManager.connSse(user);
    }
}
