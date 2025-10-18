package ssafy.com.onair.company.scheduler;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import ssafy.com.onair.company.repository.CompanyUuidRepository;

@Slf4j
@Component
@RequiredArgsConstructor
public class CompanyScheduler {
    private CompanyUuidRepository companyUuidRepository;

    @Scheduled(cron = "0 0 3 * * *")
    public void removeInvalidCompanyUUID() {
        Integer removedCompanyUUID = companyUuidRepository.removeInvalidCompanyUUID();
        log.info("Removed Invalid CompanyUUID : {}", removedCompanyUUID);
    }
}
