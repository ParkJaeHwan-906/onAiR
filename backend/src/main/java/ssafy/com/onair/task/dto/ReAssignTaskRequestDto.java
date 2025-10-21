package ssafy.com.onair.task.dto;

import lombok.Data;

@Data
public class ReAssignTaskRequestDto {
    private Long taskId;
    private Long userAccountId;
}
