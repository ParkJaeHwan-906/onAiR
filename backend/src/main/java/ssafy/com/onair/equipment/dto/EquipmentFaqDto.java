package ssafy.com.onair.equipment.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class EquipmentFaqDto {
    private Long id;
    private Long equipmentId;
    private String question;
    private String answer;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
