package ssafy.com.onair.task.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.task.service.TaskServiceImpl;

@RestController
@RequestMapping("/task")
@RequiredArgsConstructor
public class TaskController {
    private final TaskServiceImpl taskService;

    @PreAuthorize("hasRole('관리자')")
    @PostMapping("/regist")
    public ResponseEntity<ApiResponse<?>> registTask(@AuthenticationPrincipal CustomUserDetails user,
                                                    @RequestBody InsertTaskRequestDto request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(taskService.registTask(user, request)));
    }
}
