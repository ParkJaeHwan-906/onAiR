package ssafy.com.onair.global.jwt.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.global.jwt.util.JwtTokenProvider;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.user.repository.UserAccountsRepository;

import java.io.IOException;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    private final UserAccountsRepository userAccountsRepository;
    private final JwtTokenProvider jwtTokenProvider;

    public JwtAuthenticationFilter(UserAccountsRepository userAccountsRepository, JwtTokenProvider jwtTokenProvider) {
        this.userAccountsRepository = userAccountsRepository;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain) throws ServletException, IOException {
        String authHeader = request.getHeader("Authorization");
        String token = null;
        Long userAccountId = null;

        if(authHeader != null && authHeader.startsWith("Bearer ")) {
            token = authHeader.substring(7);
            if(jwtTokenProvider.validateToken(token)) {
                userAccountId = jwtTokenProvider.getUserAccountId(token);
                UserInfoDto user = userAccountsRepository.selectUserInfoByUserAccountId(userAccountId)
                        .orElseThrow(() -> new IllegalArgumentException("사용자 정보가 부정확합니다."));
                CustomUserDetails userDetails = new CustomUserDetails(user);
                UsernamePasswordAuthenticationToken authToken =
                        new UsernamePasswordAuthenticationToken(userDetails, null, userDetails.getAuthorities());

                SecurityContextHolder.getContext().setAuthentication(authToken);
            }
        }

        filterChain.doFilter(request, response);
    }
}
