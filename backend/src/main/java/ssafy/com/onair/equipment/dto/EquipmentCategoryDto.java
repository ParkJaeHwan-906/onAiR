package ssafy.com.onair.equipment.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class EquipmentCategoryDto {
    private Long id;
    private String name;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
