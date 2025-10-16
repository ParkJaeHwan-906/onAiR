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
    @NotBlank(message = "이메일은 필수입니다.")
    private String email;
    @NotBlank(message = "비밀번호는 필수입니다.")
    private String password;
}
