package ssafy.com.onair.task.service;

import ssafy.com.onair.global.jwt.user.CustomUserDetails;
import ssafy.com.onair.task.dto.InsertTaskRequestDto;

public interface TaskService {
    Boolean registTask(CustomUserDetails user, InsertTaskRequestDto request);
}
