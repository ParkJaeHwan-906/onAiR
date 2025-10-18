package ssafy.com.onair.auth.controller;

import jakarta.annotation.Nullable;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.auth.dto.LoginRequestDto;
import ssafy.com.onair.auth.dto.LoginResponseDto;
import ssafy.com.onair.auth.dto.checkInfoRequestDto;
import ssafy.com.onair.auth.dto.SignupRequestDto;
import ssafy.com.onair.auth.service.AuthServiceImpl;
import ssafy.com.onair.global.response.dto.ApiResponse;

@RestController
@RequiredArgsConstructor
@RequestMapping("/auth")
public class AuthController {
    private final AuthServiceImpl authService;

    @PostMapping("/signup")
    public ResponseEntity<ApiResponse<?>> signup(@Valid @RequestBody SignupRequestDto request, @Nullable @RequestParam String token) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(authService.signup(request, token), "회원가입이 완료되었습니다."));
    }

    @PostMapping("/check/email")
    public ResponseEntity<ApiResponse<?>> isValidEmail(@RequestBody checkInfoRequestDto request, @Nullable @PathVariable String companyUID) {
        return ResponseEntity.ok(ApiResponse.success(authService.isValidEmail(request.getEmail()), "사용 가능한 이메일입니다."));
    }

    @PostMapping("/check/password")
    public ResponseEntity<ApiResponse<?>> isValidPassword(@RequestBody checkInfoRequestDto request, @Nullable @PathVariable String companyUID) {
        return ResponseEntity.ok(ApiResponse.success(authService.isValidPassword(request.getPassword()), "사용 가능한 비밀번호입니다."));
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<LoginResponseDto>> loginRequest(@RequestBody LoginRequestDto request) {
        return ResponseEntity.ok(ApiResponse.success(authService.login(request), "로그인 되었습니다."));
    }
}
