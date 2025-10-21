package ssafy.com.onair.equipment.service;

import ssafy.com.onair.equipment.dto.EquipmentCategoryListDto;
import ssafy.com.onair.equipment.dto.EquipmentListDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentCategoryRequestDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentRequestDto;

import java.util.List;

public interface EquipmentService {
    Boolean insertEquipmentCategory(InsertEquipmentCategoryRequestDto request);
    List<EquipmentCategoryListDto> getEquipmentCategoryList();
    Boolean insertEquipment(InsertEquipmentRequestDto request);
    List<EquipmentListDto> getEquipmentList();
}
