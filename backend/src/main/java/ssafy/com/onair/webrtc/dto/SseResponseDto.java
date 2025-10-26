package ssafy.com.onair.webrtc.dto;

import lombok.Builder;

@Builder
public record SseResponseDto(
        Boolean acceptConnection,
        String accessToken
) {
}
