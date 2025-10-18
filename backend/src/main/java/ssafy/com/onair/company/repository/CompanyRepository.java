package ssafy.com.onair.company.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface CompanyRepository {
    @Insert("""
            INSERT INTO `companies`(`name`) VALUES
            (#{companyName});
            """)
    Integer insertCompany(String companyName);

    @Select("SELECT LAST_INSERT_ID();")
    Long getLastInsertedIndex();
}
