package ssafy.com.onair.equipment.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class EquipmentsDto {
    private Long id;
    private String name;
    private String image;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
