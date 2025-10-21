package ssafy.com.onair.task.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import ssafy.com.onair.global.response.dto.ApiResponse;

@RestController
@RequestMapping("/task")
@RequiredArgsConstructor
public class TaskController {
    @PreAuthorize("hasRole('관리자')")
    @PostMapping("/regist")
    public ResponseEntity<ApiResponse<?>> registTask() {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(null));
    }
}
