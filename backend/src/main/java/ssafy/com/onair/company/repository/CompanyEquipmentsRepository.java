package ssafy.com.onair.company.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import ssafy.com.onair.company.dto.CompanyEquipmentListDto;

import java.util.List;

@Mapper
public interface CompanyEquipmentsRepository {
    @Insert("""
            INSERT INTO `company_equipments`(`company_id`, `equipment_id`) VALUES
            (#{companyId}, #{equipmentId});
            """)
    Integer insertCompanyEquipments(Long companyId, Long equipmentId);

    @Select("""
            SELECT
            e.id AS 'id',
            ec.`name` AS 'category',
            e.`name` AS 'name'
            FROM `company_equipments` ce
            JOIN `equipments` e ON e.id = ce.equipment_id
            JOIN `equipment_categories` ec ON ec.id = e.equipment_category_id
            WHERE ce.company_id = #{companyId};
            """)
    List<CompanyEquipmentListDto> selectCompanyEquipmentListByCompanyId(Long companyId);
}
