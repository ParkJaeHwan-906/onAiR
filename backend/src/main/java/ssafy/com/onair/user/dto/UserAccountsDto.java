package ssafy.com.onair.user.dto;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class UserAccountsDto {
    private Long id;
    private Long userId;
    private Long companyId;
    private String email;
    private String password;
    private Long roleId;
    private Integer online;
    private Integer ban;
    private LocalDate exit;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
