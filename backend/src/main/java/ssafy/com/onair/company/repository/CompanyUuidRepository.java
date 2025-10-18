package ssafy.com.onair.company.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.Date;
import java.util.Optional;

@Mapper
public interface CompanyUuidRepository {
    @Select("""
            SELECT `company_id` FROM `company_uuid`
            WHERE `uuid` = #{companyUID}
            AND `expired_at` > NOW()
            LIMIT 1;
            """)
    Optional<Long> selectCompanyIdByUUID(String companyUID);

    @Select("""
            SELECT COUNT(*) FROM `company_uuid`
            WHERE `uuid` = #{companyUUID};
            """)
    Integer selectCountByCompanyUUID(String companyUUID);

    @Insert("""
            INSERT INTO `company_uuid`(`company_id`, `uuid`, `expired_at`)
            VALUES (#{companyId}, #{uuid}, #{expiredAt});
            """)
    Integer insertCompanyUUID(Long companyId, String uuid, Date expiredAt);
}
