package ssafy.com.onair.sse.dto;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TaskStatusChangeDto {
    private Long taskId;
}
