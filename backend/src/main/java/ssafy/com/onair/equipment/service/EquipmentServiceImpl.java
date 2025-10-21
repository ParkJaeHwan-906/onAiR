package ssafy.com.onair.equipment.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ssafy.com.onair.equipment.dto.EquipmentCategoryListDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentCategoryRequestDto;
import ssafy.com.onair.equipment.repository.EquipmentCategoriesRepository;

import java.util.List;

@Service
@RequiredArgsConstructor
public class EquipmentServiceImpl implements EquipmentService {
    private final EquipmentCategoriesRepository equipmentCategoriesRepository;

    @Transactional
    @Override
    public Boolean insertEquipmentCategory(InsertEquipmentCategoryRequestDto request) {
        return equipmentCategoriesRepository.insertEquipmentCategory(request.getEquipmentCategory()) == 1;
    }

    @Override
    public List<EquipmentCategoryListDto> getEquipmentCategoryList() {
        return equipmentCategoriesRepository.selectEquipmentCategoryLists();
    }
}
