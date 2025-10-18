package ssafy.com.onair.user.dto;

import lombok.Data;

import java.time.LocalDate;

@Data
public class UserInfoDto {
    private Long userAccountId;
    private Long companyId;
    private String company;
    private String name;
    private String phone;
    private LocalDate birth;
    private String email;
    private String role;
    private String password = null;
}
