package ssafy.com.onair.company.service;

import ssafy.com.onair.auth.dto.SignupRequestDto;

public interface CompanyService {
    SignupRequestDto fillCompanyInfo(SignupRequestDto request, String companyUID);
}
