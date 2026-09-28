SELECT
 followup.`datetime`,
 debtor.`account`,
 debtor.`card_no`,
 debtor.`name`,
 followup.`status_code`,
 followup.`remark_by`,
 followup.`created_at`
 
FROM debtor
JOIN debtor_followup ON debtor_followup.`debtor_id` = debtor.`id`
JOIN followup ON followup.`id` = debtor_followup.`followup_id`
JOIN volare.`status` ON volare.`status`.`id` = followup.`status_id`


WHERE debtor.`client_id` IN (75,77,81)
-- AND volare.`debtor`.`status_id` IN (2072,2112,2092,2147,2178,2193,2332)
AND followup.`status_id` IN (2072,2112,2092,2147,2178,2193,2332)
  
-- AND debtor.`is_aborted` = 0
-- AND debtor.`is_locked` = 0

AND debtor_followup.`created_at` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
AND debtor_followup.`created_at` <  DATE_ADD(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 1 MONTH)

-- AND followup.`datetime` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
-- AND followup.`datetime` <  DATE_ADD(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 1 MONTH)