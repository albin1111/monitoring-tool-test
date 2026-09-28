SELECT
followup.`datetime` AS "DATE",
 debtor.`account` AS "Account No.",
 debtor.`card_no` AS "Card No.",
 debtor.`name` AS "Name",
 debtor.`client_name` AS "Client",
 followup.`status_code` AS "Status",
 followup.`remark_by` AS "Enter By",
 debtor_followup.`ptp_date` AS "PTP Date",
 followup.`created_at` AS "PTP Created Date",
 debtor_followup.`ptp_amount` AS "PTP Amount"
 
FROM debtor
JOIN debtor_followup ON debtor_followup.`debtor_id` = debtor.`id`
JOIN followup ON followup.`id` = debtor_followup.`followup_id`
JOIN volare.`status` ON volare.`status`.`id` = followup.`status_id`


WHERE debtor.`client_id` IN (75,77,81)

AND followup.`status_code` LIKE "%PTP%" 
  
AND debtor.`is_aborted` = 0
AND debtor.`is_locked` = 0

AND followup.`created_at` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
AND followup.`created_at` <  DATE_ADD(CURDATE(), INTERVAL 1 DAY)

AND debtor_followup.`ptp_date` >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
AND debtor_followup.`ptp_date` <  DATE_ADD(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 1 MONTH)

ORDER BY followup.`created_at` DESC;