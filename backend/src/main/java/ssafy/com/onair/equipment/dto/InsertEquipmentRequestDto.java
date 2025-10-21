package ssafy.com.onair.equipment.dto;

import lombok.Data;

@Data
public class InsertEquipmentRequestDto {
    private Long equipmentCategoryId;
    private String equipmentName;
    private String equipmentImage;
}
