SELECT
 followup.`datetime`,
 debtor.`account`,
 debtor.`card_no`,
 debtor.`name`,
 followup.`status_code`,
 followup.`remark_by`,
 followup.`remark`,
 followup.`created_at`

FROM debtor
JOIN debtor_followup ON debtor_followup.`debtor_id` = debtor.`id`
JOIN followup ON followup.`id` = debtor_followup.`followup_id`


WHERE debtor.`client_id` IN (75,77,81)
AND  followup.`status_code` = "PAYMENT - FULLY PAID"

-- AND debtor.`is_aborted` = 0
-- AND debtor.`is_locked` = 0


AND followup.`created_at` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
AND followup.`created_at` <  DATE_ADD(CURDATE(), INTERVAL 1 DAY)

-- AND debtor_followup.`created_at` >= DATE_FORMAT(CURDATE() - INTERVAL 1 YEAR , '%Y-01-01')
-- AND debtor_followup.`created_at` <  DATE_FORMAT(CURDATE() + INTERVAL 1 YEAR, '%Y-01-01')

-- AND followup.`datetime` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
-- AND followup.`datetime` <  DATE_ADD(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 1 MONTH)