package ssafy.com.onair.auth.dto;

import lombok.Data;

@Data
public class RegenerateRefreshTokenRequestDto {
    private String refreshToken;
}
