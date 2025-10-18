package ssafy.com.onair.auth.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ssafy.com.onair.auth.dto.LoginRequestDto;
import ssafy.com.onair.auth.dto.LoginResponseDto;
import ssafy.com.onair.auth.dto.RegenerateRefreshTokenRequestDto;
import ssafy.com.onair.auth.dto.SignupRequestDto;
import ssafy.com.onair.auth.repository.RefreshTokenRepository;
import ssafy.com.onair.company.service.CompanyServiceImpl;
import ssafy.com.onair.global.jwt.util.JwtTokenProvider;
import ssafy.com.onair.global.security.config.SecurityConfig;
import ssafy.com.onair.user.dto.ValidUserAccountDto;
import ssafy.com.onair.user.repository.UserAccountsRepository;
import ssafy.com.onair.user.repository.UsersRepository;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService{
    private final String[] banKeywords = {"test", "admin", "master"};    // 이메일에 포함되면 안되는 키워드
    private final String passwordRegex = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[$@$!%*?&])[A-Za-z\\d$@$!%*?&]{8,}$";

    private final UsersRepository usersRepository;
    private final UserAccountsRepository userAccountsRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final CompanyServiceImpl companyService;
    private final RefreshTokenRepository refreshTokenRepository;

    private final SecurityConfig securityConfig;

    @Transactional
    @Override
    public boolean signup(SignupRequestDto request, String companyUID) {
        try {
            log.info("회원가입 요청 : {}", request.getEmail());
            request = companyService.fillCompanyInfo(request, companyUID);
            usersRepository.insertUser(request.getName(), request.getBirth(), request.getPhone());
            userAccountsRepository.insertUserAccounts(usersRepository.getLastUserIdx(), request.getCompanyId(), request.getEmail(), securityConfig.passwordEncoder().encode(request.getPassword()), request.getRoleId());
            return true;
        } catch(Exception e) {
            throw new IllegalArgumentException("회원가입 도중 오류가 발생했습니다.");
        }
    }

    @Override
    public Boolean isValidEmail(String email) {
        String lowerCaseEmail = email.toLowerCase();
        for(String banKeyword : banKeywords) {
            if(lowerCaseEmail.contains(banKeyword)) throw new IllegalArgumentException("사용할 수 없는 키워드가 포함되어 있습니다.");
        }

        if(userAccountsRepository.selectCountByEmail(email) == 0) return true;
        throw new IllegalArgumentException("이미 사용중인 이메일입니다.");
    }

    @Override
    public Boolean isValidPassword(String password) {
        Pattern avoidPattern = Pattern.compile(passwordRegex);
        Matcher matcher = avoidPattern.matcher(password);
        if(!matcher.matches()) throw new IllegalArgumentException("""
                비밀번호는
                -최소 8자리 이상
                -대소문자를 1개 이상 포함
                -숫자를 1개 이상 포함
                -특수문자를 1개 이상 포함
                해야합니다.
                """);
        return true;
    }

    @Transactional
    @Override
    public LoginResponseDto login(LoginRequestDto request) {
        ValidUserAccountDto validUser = userAccountsRepository.selectUserByEmail(request.getEmail())
                        .orElseThrow(() -> new IllegalArgumentException("아이디 또는 패스워드를 확인해주세요."));
        if(!securityConfig.passwordEncoder().matches(request.getPassword(), validUser.getPassword())) throw new IllegalArgumentException("아이디 또는 패스워드를 확인해주세요.");

        return LoginResponseDto.builder()
                .accessToken(jwtTokenProvider.generateAccessToken(validUser.getId()))
                .refreshToken(jwtTokenProvider.generateRefreshToken(validUser.getId()))
                .build();
    }

    @Transactional
    @Override
    public LoginResponseDto regenerateRefreshToken(RegenerateRefreshTokenRequestDto request) {
        Long userAccountId = jwtTokenProvider.getUserAccountId(request.getRefreshToken());
        if(!refreshTokenRepository.selectRefreshTokenByUserAccountId(userAccountId)
                .orElseThrow(() -> new IllegalArgumentException("유효하지 않은 토큰입니다.")).equals(request.getRefreshToken())) throw new IllegalArgumentException("유효하지 않은 토큰입니다.");
        refreshTokenRepository.deleteRefreshTokenByUserAccountId(userAccountId);
        return LoginResponseDto.builder()
                .accessToken(jwtTokenProvider.generateAccessToken(userAccountId))
                .refreshToken(jwtTokenProvider.generateRefreshToken(userAccountId))
                .build();
    }
}
