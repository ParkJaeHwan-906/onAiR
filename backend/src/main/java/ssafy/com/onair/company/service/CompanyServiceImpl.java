package ssafy.com.onair.company.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import ssafy.com.onair.auth.dto.SignupRequestDto;
import ssafy.com.onair.company.repository.CompanyRepository;
import ssafy.com.onair.company.repository.CompanyUuidRepository;

@Service
@RequiredArgsConstructor
public class CompanyServiceImpl implements CompanyService {
    private final CompanyRepository companyRepository;
    private final CompanyUuidRepository companyUuidRepository;
    @Override
    public SignupRequestDto fillCompanyInfo(SignupRequestDto request, String companyUID) {
        if(companyUID == null || companyUID.isEmpty()) {
            companyRepository.insertCompany(request.getCompanyName());
            request.setCompanyId(companyRepository.getLastInsertedIndex());
            request.setRoleId(1L);
        } else {
            request.setCompanyId(companyUuidRepository.selectCompanyIdByUUID(companyUID));
            request.setRoleId(2L);
        }
        return request;
    }
}
