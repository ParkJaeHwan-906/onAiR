package ssafy.com.onair.user.dto;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class UsersDto {
    private Long id;
    private String name;
    private LocalDate birth;
    private String phone;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
