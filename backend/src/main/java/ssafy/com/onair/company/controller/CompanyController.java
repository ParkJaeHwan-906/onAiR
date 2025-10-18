package ssafy.com.onair.company.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import ssafy.com.onair.company.dto.CompanyUuidResponseDto;
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
}
