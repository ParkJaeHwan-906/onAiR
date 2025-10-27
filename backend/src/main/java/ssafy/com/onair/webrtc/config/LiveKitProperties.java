package ssafy.com.onair.webrtc.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

// application.properties에 있는 livekit.api로 시작하는 값을 읽어옴
@ConfigurationProperties(prefix="livekit.api")
public record LiveKitProperties(
        String key,
        String secret
) {
}
