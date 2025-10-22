package ssafy.com.onair.global.jwt.user;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;
import ssafy.com.onair.user.dto.UserInfoDto;

import java.util.Collection;
import java.util.List;

public class CustomUserDetails implements UserDetails {
    private final UserInfoDto userInfo;

    public CustomUserDetails(UserInfoDto userInfo) { this.userInfo = userInfo; }

    public Long getUserAccountId() { return this.userInfo.getUserAccountId(); }
    public Long getCompanyId() { return this.userInfo.getCompanyId(); }
    public UserInfoDto getUserInfo() { return this.userInfo; }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_"+userInfo.getRole()));
    }

    @Override
    public String getPassword() {
        return null;
    }

    @Override
    public String getUsername() { return this.userInfo.getName(); }
}
