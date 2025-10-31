package ssafy.com.onair.user.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;
import ssafy.com.onair.user.dto.HrUserDto;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.user.dto.ValidUserAccountDto;

import java.util.List;
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
            ua.company_id AS 'companyId',
            c.`name` AS 'company',
            u.name AS 'name',
            u.phone AS 'phone',
            u.birth AS 'birth',
            ua.email AS 'email',
            r.role AS 'role',
            e.id AS 'equipmentId',
            e.`name` AS 'equipmentName',
            ec.id AS 'equipmentCategoryId',
            ec.`name` AS 'equipmentCategoryName'
            FROM `user_accounts` AS ua
            JOIN `users` AS u ON u.id = ua.user_id
            JOIN `roles` AS r ON r.id = ua.role_id
            JOIN `companies` AS c ON ua.company_id = c.id
            LEFT JOIN `equipments` AS e ON ua.equipment_id = e.id
            LEFT JOIN `equipment_categories` ec ON ec.id = e.equipment_category_id
            WHERE ua.id = #{userAccountId}
            AND ua.exit IS NULL
            AND ua.ban = 0;
            """)
    Optional<UserInfoDto> selectUserInfoByUserAccountId(Long userAccountId);

    @Update("""
            UPDATE `user_accounts` ua
            SET
                password = #{password}
            WHERE ua.email = #{userEmail};
            """)
    Integer updateUserInfo(String password, String userEmail);

    @Update("""
            UPDATE `user_accounts`
            SET
               `online` = 1
            WHERE `id` = #{userAccountId};
            """)
    Integer updateUserStateCheckIn(Long userAccountId);

    @Update("""
            UPDATE `user_accounts`
            SET
               `online` = 0
            WHERE `id` = #{userAccountId};
            """)
    Integer updateUserStateCheckOut(Long userAccountId);

    @Select("""
        <script>
        SELECT
            ua.id AS userAccountId,
            ua.company_id AS companyId,
            u.name AS name,
            u.phone AS phone,
            ua.email AS email,
            ua.equipment_id AS equipmentId,
            e.name AS equipmentName,
            ua.`online` AS 'online'
        FROM user_accounts AS ua
        JOIN users AS u ON u.id = ua.user_id
        LEFT JOIN `equipments` e ON e.id = ua.`equipment_id`
        WHERE ua.company_id = #{companyId}
          AND ua.id != #{userAccountId}
          AND ua.exit IS NULL
          AND ua.ban = 0
        <if test="equipmentId != null">
          AND ua.equipment_id = #{equipmentId}
        </if>
        ;
        </script>
        """)
    List<HrUserDto> getCompanyUserList(Long companyId, Long userAccountId, Long equipmentId);


    @Update("""
            UPDATE `user_accounts`
            SET
                `equipment_id` = #{equipmentId}
            WHERE `id` = #{userAccountId};
            """)
    Boolean assignEquipment(Long userAccountId, Long equipmentId);
}
