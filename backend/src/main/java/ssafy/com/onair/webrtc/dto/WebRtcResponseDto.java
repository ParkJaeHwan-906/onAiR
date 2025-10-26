package ssafy.com.onair.webrtc.dto;

public record WebRtcResponseDto(
    Long senderAccountId,
    String senderName,
    Boolean acceptConnection
) {
}
