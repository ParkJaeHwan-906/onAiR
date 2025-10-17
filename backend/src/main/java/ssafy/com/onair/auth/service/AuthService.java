package ssafy.com.onair.auth.service;

import ssafy.com.onair.auth.dto.LoginRequestDto;
import ssafy.com.onair.auth.dto.LoginResponseDto;
import ssafy.com.onair.auth.dto.SignupRequestDto;

public interface AuthService {
    boolean signup(SignupRequestDto request, String companyUID);
    Boolean isValidEmail(String email);
    Boolean isValidPassword(String password);
    LoginResponseDto login(LoginRequestDto request);
}
