package ssafy.com.onair.global.log.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import ssafy.com.onair.global.log.interceptor.RequestLoggingInterceptor;

@Configuration
@RequiredArgsConstructor
public class WebConfig implements WebMvcConfigurer {
    private final RequestLoggingInterceptor requestLoggingInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(requestLoggingInterceptor)
                .addPathPatterns("/**")  // 모든 경로에 적용
                .excludePathPatterns(    // 제외할 경로들
                        "/favicon.ico",      // 파비콘
                        "/swagger-ui/**"    // 스웨거
                );
    }
}