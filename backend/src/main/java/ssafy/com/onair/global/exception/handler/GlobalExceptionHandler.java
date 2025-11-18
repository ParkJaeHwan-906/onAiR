package ssafy.com.onair.global.exception.handler;

import io.jsonwebtoken.JwtException;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authorization.AuthorizationDeniedException;
import org.springframework.validation.BindException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import ssafy.com.onair.global.response.dto.ApiResponse;

import java.sql.SQLIntegrityConstraintViolationException;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    private boolean isSseRequest(HttpServletRequest request) {
        if (request == null) return false;

        String accept = request.getHeader("Accept");
        String contentType = request.getHeader("Content-Type");

        return (accept != null && accept.contains("text/event-stream")) ||
                (contentType != null && contentType.contains("text/event-stream"));
    }

    private ResponseEntity<?> skipForSse(HttpServletRequest request, Exception e, String type) {
        if (isSseRequest(request)) {
            log.warn("[SSE] {} ignored: {}", type, e.getMessage());
            return new ResponseEntity<>(HttpStatus.OK); // SSE엔 JSON 응답 금지
        }
        return null;
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<?> handleIllegalArgument(HttpServletRequest request, IllegalArgumentException e) {
        ResponseEntity<?> skip = skipForSse(request, e, "IllegalArgumentException");
        if (skip != null) return skip;

        log.error("IllegalArgumentException Reason : {}", e.getMessage());
        return ResponseEntity.badRequest().body(ApiResponse.fail(e.getMessage()));
    }

    @ExceptionHandler(BindException.class)
    public ResponseEntity<?> handleBindExceptions(HttpServletRequest request, BindException ex) {
        ResponseEntity<?> skip = skipForSse(request, ex, "BindException");
        if (skip != null) return skip;

        log.error("BindException Reason : {}", ex.getMessage());
        String errorMessage = ex.getBindingResult()
                .getFieldErrors()
                .stream()
                .map(error -> error.getDefaultMessage())
                .findFirst()
                .orElse("잘못된 요청입니다.");

        return ResponseEntity.badRequest().body(ApiResponse.error(errorMessage));
    }

    @ExceptionHandler(AuthorizationDeniedException.class)
    public ResponseEntity<?> handleAuthorizationDenied(HttpServletRequest request, AuthorizationDeniedException e) {
        ResponseEntity<?> skip = skipForSse(request, e, "AuthorizationDeniedException");
        if (skip != null) return skip;

        log.error("AuthorizationDeniedException Reason : {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(ApiResponse.fail("접근 권한이 없습니다."));
    }

    @ExceptionHandler(JwtException.class)
    public ResponseEntity<?> handleJwtException(HttpServletRequest request, JwtException e) {
        ResponseEntity<?> skip = skipForSse(request, e, "JwtException");
        if (skip != null) return skip;

        log.error("JwtException Reason : {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(ApiResponse.fail("인증이 필요합니다."));
    }

    @ExceptionHandler(SQLIntegrityConstraintViolationException.class)
    public ResponseEntity<?> handleSqlIntegrity(HttpServletRequest request, SQLIntegrityConstraintViolationException e) {
        ResponseEntity<?> skip = skipForSse(request, e, "SQLIntegrityConstraintViolationException");
        if (skip != null) return skip;

        log.error("SQLIntegrityConstraintViolationException Reason : {}", e.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(ApiResponse.fail("잘못된 요청입니다."));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<?> handleException(HttpServletRequest request, Exception e) {
        ResponseEntity<?> skip = skipForSse(request, e, "Exception");
        if (skip != null) return skip;

        log.error("Exception Reason : {}", e.getMessage(), e);
        return ResponseEntity.internalServerError().body(ApiResponse.fail("서버 내부 오류가 발생했습니다."));
    }
}
