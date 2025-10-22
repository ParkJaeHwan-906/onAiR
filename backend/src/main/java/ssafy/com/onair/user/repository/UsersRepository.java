package ssafy.com.onair.user.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDate;
import java.util.Optional;

@Mapper
public interface UsersRepository {
    @Insert("""
            INSERT INTO `users`(`name`, `birth`, `phone`) VALUES
            (#{name}, #{birth}, #{phone});
            """)
    Integer insertUser(String name, LocalDate birth, String phone);

    @Select("SELECT LAST_INSERT_ID()")
    Long getLastUserIdx();

    @Update("""
            UPDATE `users` u
            JOIN `user_accounts` ua ON u.id = ua.user_id
            SET
                u.name = #{userName},
                u.phone = #{userPhone},
                u.birth = #{userBirth}
            WHERE ua.email = #{userEmail};
            """)
    Integer updateUserInfo(String userName, String userPhone, LocalDate userBirth, String userEmail);

    @Select("""
            SELECT `name` FROM `users` u
            JOIN `user_accounts` ua ON u.id = ua.user_id
            WHERE ua.id = #{userAccountId};
            """)
    Optional<String> selectUserNameByUserAccountId(Long userAccountId);
}
