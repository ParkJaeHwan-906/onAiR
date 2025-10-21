package ssafy.com.onair.company.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.company.dto.CompanyUuidResponseDto;
import ssafy.com.onair.company.dto.InsertCompanyEquipmentRequestDto;
import ssafy.com.onair.company.service.CompanyServiceImpl;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.global.response.dto.ApiResponse;

@RestController
@RequiredArgsConstructor
@RequestMapping("/company")
public class CompanyController {
    private final CompanyServiceImpl companyService;

    @PreAuthorize("hasRole('관리자')")
    @GetMapping("/token")
    public ResponseEntity<ApiResponse<CompanyUuidResponseDto>> publishToken(@AuthenticationPrincipal CustomUserDetails user) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(companyService.publishToken(user.getCompanyId())));
    }

    @PreAuthorize("hasRole('관리자')")
    @PostMapping("/equipment/regist")
    public ResponseEntity<ApiResponse<Boolean>> registCompanyEquipment(@AuthenticationPrincipal CustomUserDetails user,
                                                                       @RequestBody InsertCompanyEquipmentRequestDto request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(companyService.registCompanyEquipment(user.getCompanyId(), request)));
    }

    @GetMapping("/equipment/list")
    public ResponseEntity<ApiResponse<?>> getCompanyEquipmentList(@AuthenticationPrincipal CustomUserDetails user) {
        return ResponseEntity.ok(ApiResponse.success(companyService.getCompanyEquipmentList(user.getCompanyId())));
    }
}
