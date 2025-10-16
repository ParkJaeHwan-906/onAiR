package ssafy.com.onair;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("ssafy.com.onair")
public class OnAirApplication {
	public static void main(String[] args) {
		SpringApplication.run(OnAirApplication.class, args);
	}
}
