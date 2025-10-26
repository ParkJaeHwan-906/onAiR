package ssafy.com.onair.webrtc.dto;

import lombok.Builder;

import java.time.LocalDate;

@Builder
public record SenderInfoDto(
        Long senderAccountId,
        Long companyId,
        String name,
        String phone,
        String role,
        Long equipmentId,
        String equipmentName,
        Long equipmentCategoryId,
        String equipmentCategoryName,
        String description
) {
}
