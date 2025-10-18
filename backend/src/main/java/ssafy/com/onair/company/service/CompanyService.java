package ssafy.com.onair.company.service;

import ssafy.com.onair.auth.dto.SignupRequestDto;
import ssafy.com.onair.company.dto.CompanyUuidResponseDto;

public interface CompanyService {
    SignupRequestDto fillCompanyInfo(SignupRequestDto request, String companyUID);
    CompanyUuidResponseDto publishToken(Long userAccountId);
}
