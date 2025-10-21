package ssafy.com.onair.user.service;

import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.user.dto.HrUserDto;
import ssafy.com.onair.user.dto.UserInfoDto;

import java.util.List;

public interface UserService {
    Boolean editUserInfo(UserInfoDto reqUser, UserInfoDto request);
    Boolean ValidationUserInto(String userEmail, String password);
    List<HrUserDto> getCompanyUserList(CustomUserDetails user);
    Boolean assignEquipment(Long userAccountId, Long equipmentId);
}
