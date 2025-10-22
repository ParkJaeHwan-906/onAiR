package ssafy.com.onair.sse.dto;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class SseMessageDto {
    private String eventName;
    private Object data;
}
