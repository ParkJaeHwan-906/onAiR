package ssafy.com.onair.auth.scheduler;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import ssafy.com.onair.auth.repository.RefreshTokenRepository;

@Slf4j
@Component
@RequiredArgsConstructor
public class AuthScheduler {
    private final RefreshTokenRepository refreshTokenRepository;

    @Scheduled(cron = "0 0 3 * * *")
    public void removeInvalidRefreshToken() {
        Integer removedToken = refreshTokenRepository.deleteInvalidRefreshTokens();
        log.info("Removed InValid RefreshToken : {}", removedToken);
    }
}
