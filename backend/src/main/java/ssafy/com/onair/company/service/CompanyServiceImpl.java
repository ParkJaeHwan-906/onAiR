package ssafy.com.onair.company.service;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import ssafy.com.onair.auth.dto.SignupRequestDto;
import ssafy.com.onair.company.dto.CompanyUuidResponseDto;
import ssafy.com.onair.company.repository.CompanyRepository;
import ssafy.com.onair.company.repository.CompanyUuidRepository;

import java.util.Date;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class CompanyServiceImpl implements CompanyService {
    private final CompanyRepository companyRepository;
    private final CompanyUuidRepository companyUuidRepository;

    @Value("${company.uuid.expiration}")
    private Long companyUuidExpiration;

    @Override
    public SignupRequestDto fillCompanyInfo(SignupRequestDto request, String companyUID) {
        if(companyUID == null || companyUID.isEmpty()) {
            companyRepository.insertCompany(request.getCompanyName());
            request.setCompanyId(companyRepository.getLastInsertedIndex());
            request.setRoleId(1L);
        } else {
            request.setCompanyId(companyUuidRepository.selectCompanyIdByUUID(companyUID)
                    .orElseThrow(() -> new IllegalArgumentException("관리자에게 문의해주세요.")));
            request.setRoleId(2L);
        }
        return request;
    }

    @Override
    public CompanyUuidResponseDto publishToken(Long companyId) {
        String companyUUID = UUID.randomUUID().toString();
        while(companyUuidRepository.selectCountByCompanyUUID(companyUUID) != 0) companyUUID = UUID.randomUUID().toString();
        Date expiredAt = new Date(System.currentTimeMillis()+companyUuidExpiration);
        companyUuidRepository.insertCompanyUUID(companyId, companyUUID, expiredAt);
        return CompanyUuidResponseDto.builder()
                .token(companyUUID)
                .build();
    }
}
