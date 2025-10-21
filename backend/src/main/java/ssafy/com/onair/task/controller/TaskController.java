package ssafy.com.onair.task.controller;

import jakarta.annotation.Nullable;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.task.dto.TaskListDto;
import ssafy.com.onair.task.dto.TaskStatusChangeRequestDto;
import ssafy.com.onair.task.service.TaskServiceImpl;

import java.util.List;

@RestController
@RequestMapping("/task")
@RequiredArgsConstructor
public class TaskController {
    private final TaskServiceImpl taskService;

    @PreAuthorize("hasRole('관리자')")
    @PostMapping("/regist")
    public ResponseEntity<ApiResponse<Boolean>> registTask(@AuthenticationPrincipal CustomUserDetails user,
                                                    @RequestBody InsertTaskRequestDto request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(taskService.registTask(user, request)));
    }

    @GetMapping("/list")
    public ResponseEntity<ApiResponse<List<TaskListDto>>> getTaskList(@AuthenticationPrincipal CustomUserDetails user,
                                                                      @Nullable @RequestParam Long equipmentId) {
        return ResponseEntity.ok(ApiResponse.success(taskService.getTaskList(user, equipmentId)));
    }

    @PatchMapping("/assign")
    public ResponseEntity<ApiResponse<Boolean>> assignTaskToWorker(@AuthenticationPrincipal CustomUserDetails user) {
        return ResponseEntity.ok(ApiResponse.success(taskService.assignTaskToWorker(user)));
    }

    @PatchMapping("/end")
    public ResponseEntity<ApiResponse<Boolean>> endTask(@AuthenticationPrincipal CustomUserDetails user,
                                                        @RequestBody TaskStatusChangeRequestDto request) {
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
