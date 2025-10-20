package ssafy.com.onair.equipment.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.equipment.dto.EquipmentCategoryListDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentCategoryRequestDto;
import ssafy.com.onair.equipment.service.EquipmentServiceImpl;
import ssafy.com.onair.global.response.dto.ApiResponse;

import java.util.List;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/equipment")
public class EquipmentController {
    private final EquipmentServiceImpl equipmentService;

    @PreAuthorize("hasRole('관리자')")
    @PostMapping("/category/regist")
    public ResponseEntity<ApiResponse<Boolean>> registEquipmemtCategory(@RequestBody InsertEquipmentCategoryRequestDto request) {
        /**
         * [TODO] 장비 등록 잘 되는지
         */
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(equipmentService.insertEquipmentCategory(request)));
    }

    @GetMapping("/category/list")
    public ResponseEntity<ApiResponse<List<EquipmentCategoryListDto>>> getEquipmentCategoryList() {
        /**
         * [TODO] 장비 카테고리 조회 잘 되는지
         * id, name 만 나오는지
         */
        return ResponseEntity.ok(ApiResponse.success(equipmentService.getEquipmentCategoryList()));
    }
}
