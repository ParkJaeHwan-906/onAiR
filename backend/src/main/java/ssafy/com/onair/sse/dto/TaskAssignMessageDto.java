package ssafy.com.onair.sse.dto;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TaskAssignMessageDto {
    private Long assignedTaskId;
    private Long assignedUserAccountId;
    private String assignedUserName;
}
