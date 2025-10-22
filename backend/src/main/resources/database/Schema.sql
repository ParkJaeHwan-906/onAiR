DROP DATABASE IF EXISTS `onair`;

CREATE DATABASE `onair`;

USE `onair`;

-- 회원정보 --
CREATE TABLE `roles`(
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`role` VARCHAR(10) NOT NULL COMMENT '권한(관리자, 일반 유저)',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '권한정보를 저장';

INSERT INTO `roles`(`role`) VALUES ('관리자'), ('사용자');

CREATE TABLE `companies` (
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`name` VARCHAR(255) NOT NULL COMMENT '회사명',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) COMMENT '가입된 기업 정보를 저장';

CREATE TABLE `company_uuid` (
	`company_id` BIGINT NOT NULL,
	`uuid` VARCHAR(36) NOT NULL UNIQUE KEY,
	`expired_at` DATETIME NOT NULL,
	FOREIGN KEY(`company_id`) REFERENCES `companies`(`id`)
) COMMENT '기업 내 직원 관리를 위한 UUID 저장';

-- 설비 정보 --
CREATE TABLE `equipment_categories`(
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`name` VARCHAR(255) NOT NULL COMMENT '설비의 카테고리',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '설비의 분류 저장';

CREATE TABLE `equipments` (
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`equipment_category_id` BIGINT NOT NULL COMMENT 'equipment_categories 테이블의 id와 FK',
	`name` VARCHAR(255) NOT NULL COMMENT '설비 이름',
	`image` VARCHAR(255) DEFAULT NULL COMMENT '설비 사진url (S3 endPoint)',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	FOREIGN KEY(`equipment_category_id`) REFERENCES `equipment_categories`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE
) COMMENT '설비 목록을 저장';

CREATE TABLE `company_equipments` (
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`company_id` BIGINT NOT NULL COMMENT 'companies 테이블의 id 와 FK',
	`equipment_id` BIGINT NOT NULL COMMENT 'equipments 테이블의 id 와 FK',
	`deleted` DATETIME DEFAULT NULL COMMENT '해당 설비의 사용 여부',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	FOREIGN KEY(`company_id`) REFERENCES `companies`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE,
	FOREIGN KEY(`equipment_id`) REFERENCES `equipments`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE
) COMMENT '각 회사의 설비를 저장';

-- RAG 목적 설비별 FAQ --
CREATE TABLE `equipment_faq` (
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`equipment_id` BIGINT NOT NULL COMMENT 'equipments 테이블의 id 와 FK',
	`question` TEXT NOT NULL COMMENT '메뉴얼 및 이전 이력에 대한 내용',
	`answer` TEXT NOT NULL COMMENT '해결 방법',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	FOREIGN KEY(`equipment_id`) REFERENCES `equipments`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE
) COMMENT '각 설비의 이전 작업 이력 및 메뉴얼 내용';

CREATE TABLE `users`(
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`name` VARCHAR(30) NOT NULL COMMENT '사용자 이름',
	`birth` DATE NOT NULL COMMENT '사용자 생년월일',
	`phone` VARCHAR(11) NOT NULL COMMENT '사용자 휴대폰 번호',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '사용자의 기본 정보를 저장';

CREATE TABLE `user_accounts`(
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
	`user_id` BIGINT NOT NULL COMMENT 'users 테이블의 id 와 FK',
	`company_id` BIGINT NOT NULL COMMENT 'company 테이블의 id 와 FK',
	`email` VARCHAR(100) NOT NULL UNIQUE KEY COMMENT '계정 id 로 사용할 이메일',
	`password` VARCHAR(255) NOT NULL COMMENT '계정 패스워드',
	`role_id` BIGINT NOT NULL DEFAULT 2 COMMENT '계정의 권한 ( 기본은 사용자 )',
	`online` TINYINT NOT NULL DEFAULT 0 COMMENT '온라인(출근) 여부 ( 0 : X, 1 : O )',
	`equipment_id` BIGINT DEFAULT NULL COMMENT 'equipments 테이블의 id와 FK (주 담당 설비)',
	`ban` TINYINT NOT NULL DEFAULT 0 COMMENT '계정의 ban 여부를 확인 ( 0 : X, 1 : O )',
	`exit` DATE DEFAULT NULL COMMENT '계정의 탈퇴 여부를 확인',
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	FOREIGN KEY(`equipment_id`) REFERENCES `equipments`(`id`)
    		ON UPDATE CASCADE
    		ON DELETE CASCADE,
	FOREIGN KEY(`role_id`) REFERENCES `roles`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE,
	FOREIGN KEY(`company_id`) REFERENCES `companies`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE,
	FOREIGN KEY(`user_id`) REFERENCES `users`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE
) COMMENT '사용자의 계정 정보를 저장';

CREATE TABLE `refresh_token`(
	`user_account_id` BIGINT NOT NULL,
	`refresh_token` VARCHAR(255) NOT NULL,
	`expired_at` DATETIME NOT NULL,
	FOREIGN KEY(`user_account_id`) REFERENCES `user_accounts`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE
) COMMENT '사용자의 리프레쉬 토큰 정보를 저장';

CREATE TABLE attendance (
     `user_account_id` BIGINT NOT NULL,
     `work_date` DATE NOT NULL,
     `check_in_time` DATETIME DEFAULT NULL,
     `check_out_time` DATETIME DEFAULT NULL,
     `total_work_minutes` INT DEFAULT NULL,
     PRIMARY KEY (`user_account_id`, `work_date`),
 	 FOREIGN KEY (`user_account_id`) REFERENCES `user_accounts`(`id`)
         ON DELETE CASCADE
         ON UPDATE CASCADE
 ) COMMENT '근로자들의 근태관리를 위한 테이블';

-- 업무 --
-- CREATE TABLE `task_bundles`(
-- 	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
-- 	`company_id` BIGINT NOT NULL,
-- 	`code` VARCHAR(255) NOT NULL COMMENT '업무 코드',
-- 	`user_account_id` BIGINT NOT NULL,
-- 	`action` INT DEFAULT 1 COMMENT '0 : 취소, 1 : 진행 전, 2 : 진행중, 3 : 완료',
-- 	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
-- 	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
-- 	FOREIGN KEY(`company_id`) REFERENCES `companies`(`id`)
-- 		ON UPDATE CASCADE
-- 		ON DELETE CASCADE,
-- 	FOREIGN KEY(`user_account_id`) REFERENCES `user_accounts`(`id`)
-- 		ON UPDATE CASCADE
-- 		ON DELETE CASCADE
-- ) COMMENT '업무 목록을 저장하는 테이블';


CREATE TABLE `tasks`(
	`id` BIGINT AUTO_INCREMENT PRIMARY KEY,
--	`task_bundle_id` BIGINT NOT NULL,
	`equipment_id` BIGINT NOT NULL,
	`company_id` BIGINT NOT NULL,
	`user_account_id`BIGINT DEFAULT NULL COMMENT '업무 책임자',
--	`address` TEXT NOT NULL COMMENT '업무를 진행할 위치 (도로명 주소)',
	`request` TEXT NOT NULL COMMENT '업무 요청사항',
	`action` INT DEFAULT 1 COMMENT '0 : 취소, 1 : 진행 전, 2 : 진행중, 3 : 완료',
	`solution` TEXT DEFAULT NULL,
	`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
--	FOREIGN KEY(`task_bundle_id`) REFERENCES `task_bundles`(`id`)
--		ON UPDATE CASCADE
--		ON DELETE CASCADE,
	FOREIGN KEY(`equipment_id`) REFERENCES `equipments`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE,
	FOREIGN KEY(`company_id`) REFERENCES `companies`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE,
	FOREIGN KEY(`user_account_id`) REFERENCES `user_accounts`(`id`)
		ON UPDATE CASCADE
		ON DELETE CASCADE
) COMMENT '업무 목록을 저장하는 테이블';