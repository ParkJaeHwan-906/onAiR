package ssafy.com.onair.user.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.user.dto.ValidUserAccountDto;

import java.util.Optional;

@Mapper
public interface UserAccountsRepository {
    @Insert("""
            INSERT INTO `user_accounts`(`user_id`, `company_id`, `email`, `password`, `role_id`) VALUES
            (#{userId}, #{companyId}, #{email}, #{password}, #{roleId});
            """)
    Integer insertUserAccounts(Long userId, Long companyId, String email, String password, Long roleId);

    @Select("""
            SELECT COUNT(*) FROM `user_accounts`
            WHERE `email` LIKE #{email};
            """)
    Integer selectCountByEmail(String email);

    @Select("""
            SELECT id, password FROM `user_accounts`
            WHERE email LIKE #{email}
            AND `ban` = 0
            AND `exit` IS NULL;
            """)
    Optional<ValidUserAccountDto> selectUserByEmail(String email);

    @Select("""
            SELECT
            ua.id AS 'userAccountId',
            u.name AS 'name',
            u.phone AS 'phone',
            u.birth AS 'birth',
            ua.email AS 'email',
            r.role AS 'role'
            FROM `user_accounts` AS ua
            JOIN `users` AS u ON u.id = ua.user_id
            JOIN `roles` AS r ON r.id = ua.role_id
            WHERE ua.id = #{userAccountId};
            """)
    Optional<UserInfoDto> selectUserInfoByUserAccountId(Long userAccountId);

    @Update("""
            UPDATE `user_accounts` ua
            SET
                password = #{password}
            WHERE ua.email = #{userEmail};
            """)
    Integer updateUserInfo(String password, String userEmail);
}
