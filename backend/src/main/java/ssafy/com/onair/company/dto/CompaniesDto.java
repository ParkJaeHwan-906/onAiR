package ssafy.com.onair.company.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class CompaniesDto {
    private Long id;
    private String name;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
