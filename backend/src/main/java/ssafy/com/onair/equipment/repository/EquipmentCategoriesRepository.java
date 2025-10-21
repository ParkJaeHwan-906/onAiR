package ssafy.com.onair.equipment.repository;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import ssafy.com.onair.equipment.dto.EquipmentCategoryDto;
import ssafy.com.onair.equipment.dto.EquipmentCategoryListDto;

import java.util.List;

@Mapper
public interface EquipmentCategoriesRepository {
    @Insert("""
            INSERT INTO `equipment_categories`(`name`)
            VALUES (#{equipmentName});
            """)
    Integer insertEquipmentCategory(String equipmentName);

    @Select("""
            SELECT
            `id`,
            `name`
            FROM `equipment_categories`;
            """)
    List<EquipmentCategoryListDto> selectEquipmentCategoryLists();
}
