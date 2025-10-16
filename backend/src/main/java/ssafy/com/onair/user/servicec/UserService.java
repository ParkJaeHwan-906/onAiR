package ssafy.com.onair.user.servicec;

import ssafy.com.onair.user.dto.UserInfoDto;

public interface UserService {
    Boolean editUserInfo(UserInfoDto reqUser, UserInfoDto request);
    Boolean ValidationUserInto(String userEmail, String password);
}
