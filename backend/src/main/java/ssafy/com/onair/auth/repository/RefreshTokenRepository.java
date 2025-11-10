package ssafy.com.onair.auth.repository;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.Date;
import java.util.Optional;

@Mapper
public interface RefreshTokenRepository {
    @Insert("""
            INSERT INTO `refresh_token`(`user_account_id`, `refresh_token`, `expired_at`) VALUES
            (#{userAccountId}, #{refreshToken}, #{expiredAt});
            """)
    Integer insertRefreshToken(Long userAccountId, String refreshToken, Date expiredAt);

    @Select("""
            SELECT `refresh_token` FROM `refresh_token`
            WHERE `user_account_id` = #{userAccountId}
            AND `expired_at` > NOW()
            AND `refresh_token` = #{refreshToken}
            LIMIT 1;
            """)
    Optional<String> selectRefreshTokenByUserAccountId(Long userAccountId, String refreshToken);

    @Delete("""
            DELETE FROM `refresh_token`
            WHERE `user_account_id` = #{userAccountId};
            """)
    Integer deleteRefreshTokenByUserAccountId(Long userAccountId);

    @Delete("""
            DELETE FROM `refresh_token`
            WHERE `expired_at` <= NOW();
            """)
    Integer deleteInvalidRefreshTokens();
}
