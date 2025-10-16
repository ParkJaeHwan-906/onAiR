package ssafy.com.onair.company.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class CompanyEquipmentsDto {
    private Long id;
    private Long companyId;
    private Long equipmentId;
    private String name;
    private LocalDateTime deleted;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
