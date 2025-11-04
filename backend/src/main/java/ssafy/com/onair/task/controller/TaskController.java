package ssafy.com.onair.task.controller;

import jakarta.annotation.Nullable;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.sse.manager.SseManager;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;
import ssafy.com.onair.global.response.dto.ApiResponse;
import ssafy.com.onair.task.dto.ReAssignTaskRequestDto;
import ssafy.com.onair.task.dto.TaskListDto;
import ssafy.com.onair.task.dto.TaskStatusChangeRequestDto;
import ssafy.com.onair.task.service.TaskServiceImpl;

import java.util.List;

@RestController
@RequestMapping("/task")
@RequiredArgsConstructor
public class TaskController {
    private final TaskServiceImpl taskService;
    private final SseManager sseManager;

    @PreAuthorize("hasRole('관리자')")
    @PostMapping("/regist")
    public ResponseEntity<ApiResponse<Boolean>> registTask(@AuthenticationPrincipal CustomUserDetails user,
                                                    @RequestBody InsertTaskRequestDto request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(taskService.registTask(user, request)));
    }

    @GetMapping("/list")
    public ResponseEntity<ApiResponse<List<TaskListDto>>> getTaskList(@AuthenticationPrincipal CustomUserDetails user,
                                                                      @Nullable @RequestParam Long equipmentId,
                                                                      @Nullable @RequestParam Integer action) {
        return ResponseEntity.ok(ApiResponse.success(taskService.getTaskList(user, equipmentId, action)));
    }

    @PatchMapping("/assign")
    public ResponseEntity<ApiResponse<Boolean>> assignTaskToWorker(@AuthenticationPrincipal CustomUserDetails user) {
        return ResponseEntity.ok(ApiResponse.success(taskService.assignTaskToWorker(user)));
    }

    @PatchMapping("/end")
    public ResponseEntity<ApiResponse<Boolean>> endTask(@AuthenticationPrincipal CustomUserDetails user,
                                                        @RequestBody TaskStatusChangeRequestDto request) {
        return ResponseEntity.ok(ApiResponse.success(taskService.endTask(user, request)));
    }

    @PatchMapping("/cancel")
    public ResponseEntity<ApiResponse<Boolean>> cancelTask(@AuthenticationPrincipal CustomUserDetails user,
                                                        @RequestBody TaskStatusChangeRequestDto request) {
        return ResponseEntity.ok(ApiResponse.success(taskService.cancelTask(user, request)));
    }

    @PreAuthorize("hasRole('관리자')")
    @PatchMapping("/assign/re")
    public ResponseEntity<ApiResponse<Boolean>> reAssignTask(@AuthenticationPrincipal CustomUserDetails user,
                                                             @RequestBody ReAssignTaskRequestDto request) {
        return ResponseEntity.ok(ApiResponse.success(taskService.reAssignTask(user, request)));
    }

    // TODO: deprecated -> SseController로 이동함 -> 문제 없으면 지우자!
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter connectSse(@AuthenticationPrincipal CustomUserDetails user) {
        return sseManager.connSse(user);
    }
}
