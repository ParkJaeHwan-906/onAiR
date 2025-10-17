package ssafy.com.onair.user.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ssafy.com.onair.global.security.config.SecurityConfig;
import ssafy.com.onair.user.dto.UserInfoDto;
import ssafy.com.onair.user.repository.UserAccountsRepository;
import ssafy.com.onair.user.repository.UsersRepository;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {
    private final UsersRepository usersRepository;
    private final UserAccountsRepository userAccountsRepository;
    private final SecurityConfig securityConfig;

    @Transactional
    @Override
    public Boolean editUserInfo(UserInfoDto reqUser, UserInfoDto request) {
        if(reqUser.getUserAccountId() != request.getUserAccountId()) throw new IllegalArgumentException("잘못된 요청입니다.");
        usersRepository.updateUserInfo(request.getName(), request.getPhone(), request.getBirth(), request.getEmail());
        if(request.getPassword() != null) userAccountsRepository.updateUserInfo(securityConfig.passwordEncoder().encode(request.getPassword()), request.getEmail());
        return true;
    }

    @Override
    public Boolean ValidationUserInto(String userEmail, String password) {
         if(!securityConfig.passwordEncoder().matches(password, userAccountsRepository.selectUserByEmail(userEmail)
                .orElseThrow(() -> new IllegalArgumentException("잘못된 요청입니다.")).getPassword())) throw new IllegalArgumentException("잘못된 사용자입니다.");
         return true;
    }
}
