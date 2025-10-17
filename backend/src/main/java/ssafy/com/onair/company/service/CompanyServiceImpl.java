package ssafy.com.onair.company.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import ssafy.com.onair.auth.dto.SignupRequestDto;

@Service
@RequiredArgsConstructor
public class CompanyServiceImpl implements CompanyService {
    @Override
    public SignupRequestDto fillCompanyInfo(SignupRequestDto request, String companyUID) {
        if(companyUID == null || companyUID.isEmpty()) {

        } else {

        }
        return request;
    }
}
