package ssafy.com.onair.company.service;

import ssafy.com.onair.auth.dto.SignupRequestDto;
import ssafy.com.onair.company.dto.CompanyEquipmentListDto;
import ssafy.com.onair.company.dto.CompanyUuidResponseDto;
import ssafy.com.onair.company.dto.InsertCompanyEquipmentRequestDto;

import java.util.List;

public interface CompanyService {
    SignupRequestDto fillCompanyInfo(SignupRequestDto request, String companyUID);
    CompanyUuidResponseDto publishToken(Long userAccountId);
    Boolean registCompanyEquipment(Long companyId, InsertCompanyEquipmentRequestDto request);
    List<CompanyEquipmentListDto> getCompanyEquipmentList(Long companyId);
}
