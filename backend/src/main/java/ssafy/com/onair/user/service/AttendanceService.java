package ssafy.com.onair.user.service;

public interface AttendanceService {
    String checkIn(Long userAccountId);
    String checkOut(Long userAccountId);
}
