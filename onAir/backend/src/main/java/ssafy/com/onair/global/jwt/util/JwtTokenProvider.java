package ssafy.com.onair.global.jwt.util;

import io.jsonwebtoken.*;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.security.Key;
import java.util.Date;

@Slf4j
@Component
public class JwtTokenProvider {
    private final long accessTokenExp;
    private final long refreshTokenExp;
    private final Key key;

    public JwtTokenProvider(
            @Value("${jwt.secret}") String secretKey,
            @Value("${jwt.access-token-expiration}") long accessTokenExp,
            @Value("${jwt.refresh-token-expiration}") long refreshTokenExp) {

        this.key = Keys.hmacShaKeyFor(Decoders.BASE64.decode(secretKey));
        this.accessTokenExp = accessTokenExp;
        this.refreshTokenExp = refreshTokenExp;
    }
    public String generateAccessToken(Long userAccountId) {
        return Jwts.builder()
                .setSubject(String.valueOf(userAccountId))
                .claim("type", "access")
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis()+accessTokenExp))
                .signWith(key)
                .compact();
    }

    public String generateRefreshToken(Long userAccountId) {
        return Jwts.builder()
                .setSubject(String.valueOf(userAccountId))
                .claim("type", "refresh")
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis()+refreshTokenExp))
                .signWith(key)
                .compact();
    }

    public Claims getClaims(String token) {
        try {
            return Jwts.parser()
                    .setSigningKey(key)
                    .build()
                    .parseClaimsJws(token)
                    .getBody();
        } catch (ExpiredJwtException e) {
            log.error("토큰 만료 : {}", e.getMessage());
            throw new JwtException("토큰이 만료되었습니다.");
        } catch (JwtException e) {
            log.error("토큰 검증 실패 : {}", e.getMessage());
            throw new JwtException("토큰 검증에 실패하였습니다.");
        }
    }

    public Long getUserAccountId(String token) {
        Claims claims = getClaims(token);
        return Long.parseLong(claims.getSubject());
    }

    public boolean validateToken(String token) {
        try {
            getClaims(token);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
