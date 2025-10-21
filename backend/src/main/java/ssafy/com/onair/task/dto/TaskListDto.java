package ssafy.com.onair.task.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class TaskListDto {
    private Long id;
    private Long equipmentId;
    private String equipmentName;
    private String request;
    private Long userAccountId;
    private String userName;
    private Integer action;
    private String actionStatus;
    private String solution;
    private LocalDateTime lastUpdateTime;
    
    public void mapAction() {
        switch (this.action) {
            case 0:
                this.actionStatus = "취소됨";
                break;
            case 1:
                this.actionStatus = "대기중";
                break;
            case 2:
                this.actionStatus = "작업중";
                break;
            case 3:
                this.actionStatus = "완료";
                break;
        }
    }
}
