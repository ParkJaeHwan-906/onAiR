package ssafy.com.onair.user.dto;

import lombok.Data;

@Data
public class HrUserDto {
    private Long userAccountId;
    private String name;
    private String phone;
    private String email;
    private Long equipmentId;
    private String equipmentName;
}
