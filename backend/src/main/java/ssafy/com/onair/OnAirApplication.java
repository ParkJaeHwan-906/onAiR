package ssafy.com.onair;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;
import ssafy.com.onair.webrtc.config.LiveKitProperties;

@SpringBootApplication
@EnableScheduling
@EnableConfigurationProperties(LiveKitProperties.class)
@MapperScan("ssafy.com.onair")
public class OnAirApplication {
	public static void main(String[] args) {
		SpringApplication.run(OnAirApplication.class, args);
	}
}
