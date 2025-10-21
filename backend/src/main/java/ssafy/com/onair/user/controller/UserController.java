package ssafy.com.onair.user.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.equipment.dto.AssignEquipmentRequestDto;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.user.dto.ValidationUserRequestDto;
import ssafy.com.onair.user.service.AttendanceServiceImpl;
import ssafy.com.onair.user.service.UserServiceImpl;

@RestController
@RequestMapping("/user")
@RequiredArgsConstructor
public class UserController {
    private final UserServiceImpl userService;
    private final AttendanceServiceImpl attendanceService;

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

    @GetMapping("/check/in")
    public ResponseEntity<ApiResponse<String>> checkIn(@AuthenticationPrincipal CustomUserDetails user) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(attendanceService.checkIn(user.getUserAccountId())));
    }

    @GetMapping("/check/out")
    public ResponseEntity<ApiResponse<String>> checkOut(@AuthenticationPrincipal CustomUserDetails user) {
        return ResponseEntity.ok(ApiResponse.success(attendanceService.checkOut(user.getUserAccountId())));
    }

    @PreAuthorize("hasRole('관리자')")
    @GetMapping("/list")
    public ResponseEntity<ApiResponse<?>> getCompanyUserList(@AuthenticationPrincipal CustomUserDetails user) {
        /**
         * [TODO] 직원이 하나도 없을 때는?
         */
        return ResponseEntity.ok(ApiResponse.success(userService.getCompanyUserList(user)));
    }

    @PreAuthorize("hasRole('관리자')")
    @PatchMapping("/equipment")
    public ResponseEntity<ApiResponse<Boolean>> assignEquipment(@RequestBody AssignEquipmentRequestDto request) {
        /**
         * [TODO] 장비 할당 잘 되는지?
         */
        return ResponseEntity.ok(ApiResponse.success(userService.assignEquipment(request.getUserAccountId(), request.getEquipmentId())));
    }
}
