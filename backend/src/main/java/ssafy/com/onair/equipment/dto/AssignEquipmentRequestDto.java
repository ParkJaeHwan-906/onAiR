package ssafy.com.onair.equipment.dto;

import lombok.Data;

@Data
public class AssignEquipmentRequestDto {
    private Long userAccountId;     // 할당하고자 하는 user id
    private Long equipmentId;       // 할당하고자 하는 equipment id
}
