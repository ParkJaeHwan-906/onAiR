package ssafy.com.onair.task.dto;

import lombok.Data;

@Data
public class TaskStatusChangeRequestDto {
    private Long taskId;
    private String solution = "";        // 작업 완료/취소 세부 내용
}
