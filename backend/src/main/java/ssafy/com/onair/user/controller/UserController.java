package ssafy.com.onair.user.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.user.dto.ValidationUserRequestDto;
import ssafy.com.onair.user.service.UserServiceImpl;

@RestController
@RequestMapping("/user")
@RequiredArgsConstructor
public class UserController {
    private final UserServiceImpl userService;

    @GetMapping("/detail")
    public ResponseEntity<ApiResponse<UserInfoDto>> userDetail(@AuthenticationPrincipal CustomUserDetails user) {
        return ResponseEntity.ok(ApiResponse.success(user.getUserInfo()));
    }

    @PatchMapping("/edit")
    public ResponseEntity<ApiResponse<Boolean>> editUserInfo(@AuthenticationPrincipal CustomUserDetails user, @RequestBody UserInfoDto request) {
        return ResponseEntity.ok(ApiResponse.success(userService.editUserInfo(user.getUserInfo(), request)));
    }

    @PostMapping("/validation")
    public ResponseEntity<ApiResponse<Boolean>> validationUserInfo(@AuthenticationPrincipal CustomUserDetails user, @RequestBody ValidationUserRequestDto request) {
        return ResponseEntity.ok(ApiResponse.success(userService.ValidationUserInto(user.getUserInfo().getEmail(), request.getPassword()), "인증되었습니다."));
    }
}
