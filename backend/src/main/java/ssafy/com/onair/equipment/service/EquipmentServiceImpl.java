package ssafy.com.onair.equipment.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ssafy.com.onair.equipment.dto.EquipmentCategoryListDto;
import ssafy.com.onair.equipment.dto.EquipmentListDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentCategoryRequestDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentRequestDto;
import ssafy.com.onair.equipment.repository.EquipmentCategoriesRepository;
import ssafy.com.onair.equipment.repository.EquipmentsRepository;

import java.util.List;

@Service
@RequiredArgsConstructor
public class EquipmentServiceImpl implements EquipmentService {
    private final EquipmentCategoriesRepository equipmentCategoriesRepository;
    private final EquipmentsRepository equipmentsRepository;

    @Transactional
    @Override
    public Boolean insertEquipmentCategory(InsertEquipmentCategoryRequestDto request) {
        return equipmentCategoriesRepository.insertEquipmentCategory(request.getEquipmentCategory()) == 1;
    }

    @Override
    public List<EquipmentCategoryListDto> getEquipmentCategoryList() {
        return equipmentCategoriesRepository.selectEquipmentCategoryLists();
    }

    @Override
    public Boolean insertEquipment(InsertEquipmentRequestDto request) {
        return equipmentsRepository.insertEquipment(request.getEquipmentCategoryId(), request.getEquipmentName()) == 1;
    }

    @Override
    public List<EquipmentListDto> getEquipmentList() {
        return equipmentsRepository.selectEquipmentList();
    }
}
