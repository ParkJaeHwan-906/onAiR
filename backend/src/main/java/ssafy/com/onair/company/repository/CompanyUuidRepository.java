package ssafy.com.onair.company.repository;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface CompanyUuidRepository {
    @Select("""
            SELECT `company_id` FROM `company_uuid`
            WHERE `uuid` = #{companyUID}
            AND `expired_at` > NOW()
            LIMIT 1;
            """)
    Long selectCompanyIdByUUID(String companyUID);
}
