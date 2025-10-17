package ssafy.com.onair.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.time.LocalDate;

@Data
public class SignupRequestDto {
    @NotBlank(message = "이름은 필수입니다.")
    private String name;
    @NotNull(message = "생년월일은 필수입니다.")
    private LocalDate birth;
    @NotBlank(message = "전화번호는 필수입니다.")
    private String phone;
    // 회사 정보를 동적으로 헐덩
    private String companyName;
    private Long companyId;
    private Long roleId;        // companyName 으로 들어오면 관리자로 판단
    @NotBlank(message = "이메일은 필수입니다.")
    private String email;
    @NotBlank(message = "비밀번호는 필수입니다.")
    private String password;
}
