package ssafy.com.onair.global.exception.handler;

import io.jsonwebtoken.JwtException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authorization.AuthorizationDeniedException;
import org.springframework.validation.BindException;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import ssafy.com.onair.global.response.dto.ApiResponse;

import java.sql.SQLIntegrityConstraintViolationException;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiResponse<Object>> handleIllegalArgument(IllegalArgumentException e) {
        log.error("IllegalArgumentException Reason : {}", e.getMessage());
        return ResponseEntity.badRequest().body(ApiResponse.fail(e.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Object>> handleException(Exception e) {
        log.error("Exception Reason : {}", e.getMessage());
        return ResponseEntity.internalServerError().body(ApiResponse.fail("서버 내부 오류가 발생했습니다."));
    }

    @ExceptionHandler(BindException.class)
    public ResponseEntity<ApiResponse<?>> handleBindExceptions(BindException ex) {
        log.error("handleBindExceptions Reason : {}", ex.getMessage());
        String errorMessage = ex.getBindingResult()
                .getFieldErrors()
                .stream()
                .map(error -> error.getDefaultMessage())
                .findFirst()
                .orElse("잘못된 요청입니다.");

        return ResponseEntity
                .badRequest()
                .body(ApiResponse.error(errorMessage));
    }

    @ExceptionHandler(AuthorizationDeniedException.class)
    public ResponseEntity<ApiResponse<Object>> handleAuthorizationDeniedException(AuthorizationDeniedException e) {
        log.error("AuthorizationDeniedException Reason : {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.fail("접근 권한이 없습니다."));
    }

    @ExceptionHandler(JwtException.class)
    public ResponseEntity<ApiResponse<Object>> handleJwtException(JwtException e) {
        log.error("JwtException Reason : {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.fail("인증이 필요합니다."));
    }

    @ExceptionHandler(SQLIntegrityConstraintViolationException.class)
    public ResponseEntity<ApiResponse<Object>> handleJwtException(SQLIntegrityConstraintViolationException e) {
        log.error("SQLIntegrityConstraintViolationException Reason : {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(ApiResponse.fail("잘못된 요청입니다."));
    }
}
