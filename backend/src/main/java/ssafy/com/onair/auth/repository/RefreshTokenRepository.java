package ssafy.com.onair.auth.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

import java.util.Date;

@Mapper
public interface RefreshTokenRepository {
    @Insert("""
            INSERT INTO `refresh_token`(`user_account_id`, `refresh_token`, `expired_at`) VALUES
            (#{userAccountId}, #{refreshToken}, #{expiredAt});
            """)
    Integer insertRefreshToken(Long userAccountId, String refreshToken, Date expiredAt);
}
