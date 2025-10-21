package ssafy.com.onair.equipment.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import ssafy.com.onair.equipment.dto.EquipmentListDto;

import java.util.List;

@Mapper
public interface EquipmentsRepository {
    @Insert("""
            INSERT INTO `equipments`(`equipment_category_id`, `name`) VALUES
            (#{equipmentCategoryId}, #{name});
            """)
    Integer insertEquipment(Long equipmentCategoryId, String name);

    @Select("""
            SELECT
            e.id AS 'id',
            ec.name AS 'category',
            e.name AS 'name'
            FROM `equipments` e
            JOIN `equipment_categories` ec ON e.equipment_category_id = ec.id;
            """)
    List<EquipmentListDto> selectEquipmentList();
}
