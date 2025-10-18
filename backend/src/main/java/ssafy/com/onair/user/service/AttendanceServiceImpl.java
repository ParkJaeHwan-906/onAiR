package ssafy.com.onair.user.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ssafy.com.onair.user.dto.AttendanceDto;
import ssafy.com.onair.user.repository.AttendanceRepository;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class AttendanceServiceImpl implements AttendanceService {
    private final AttendanceRepository attendanceRepository;

    @Transactional
    @Override
    public String checkIn(Long userAccountId) {
        try {
            attendanceRepository.insertCheckIn(userAccountId, LocalDate.now(), LocalDateTime.now());
            return "정상적으로 출근처리 되었습니다.";
        } catch (Exception e) {
            throw new IllegalArgumentException("이미 출근처리 되었습니다.");
        }
    }

    @Transactional
    @Override
    public String checkOut(Long userAccountId) {
        LocalDate today = LocalDate.now();
        AttendanceDto attendance = attendanceRepository.findByUserAndDate(userAccountId, today);
        if (attendance == null || attendance.getCheckInTime() == null) {
            throw new IllegalArgumentException("출근 기록이 없습니다.");
        }

        LocalDateTime checkOutTime = LocalDateTime.now();
        int totalMinutes = (int) Duration.between(attendance.getCheckInTime(), checkOutTime).toMinutes();

        attendanceRepository.updateCheckOut(userAccountId, today, checkOutTime, totalMinutes);
        return "정상적으로 퇴근처리 되었습니다.";
    }
}
