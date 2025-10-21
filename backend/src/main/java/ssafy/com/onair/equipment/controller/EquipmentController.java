package ssafy.com.onair.equipment.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.equipment.dto.EquipmentCategoryListDto;
import ssafy.com.onair.equipment.dto.EquipmentListDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentCategoryRequestDto;
import ssafy.com.onair.equipment.dto.InsertEquipmentRequestDto;
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
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(equipmentService.insertEquipmentCategory(request)));
    }

    @GetMapping("/category/list")
    public ResponseEntity<ApiResponse<List<EquipmentCategoryListDto>>> getEquipmentCategoryList() {
        return ResponseEntity.ok(ApiResponse.success(equipmentService.getEquipmentCategoryList()));
    }

    @PreAuthorize("hasRole('관리자')")
    @PostMapping("/regist")
    public ResponseEntity<ApiResponse<Boolean>> registEquipment(@RequestBody InsertEquipmentRequestDto request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(equipmentService.insertEquipment(request)));
    }

    @GetMapping("/list")
    public ResponseEntity<ApiResponse<List<EquipmentListDto>>> getEquipmentList() {
        return ResponseEntity.ok(ApiResponse.success(equipmentService.getEquipmentList()));
    }
}
