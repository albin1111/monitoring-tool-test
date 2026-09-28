SELECT
followup.`datetime`,
 debtor.`account`,
 debtor.`card_no`,
 debtor.`name`,
 debtor.`client_name`,
 followup.`status_code`,
 followup.`remark_by`,
 followup.`created_at`,
 debtor_followup.`claim_paid_date`,
 debtor_followup.`claim_paid_amount`
FROM debtor
JOIN debtor_followup ON debtor_followup.`debtor_id` = debtor.`id`
JOIN followup ON followup.`id` = debtor_followup.`followup_id`
JOIN volare.`status` ON volare.`status`.`id` = followup.`status_id`
WHERE debtor.`client_id` IN (75,77,81)
-- AND volare.status.`id` IN (2063,2074,2094,2129,2156,2184,2324)
AND followup.`status_code` IN (
"CEASE COLL EFFORT SBC - CLAIMING PAID",
"EMAIL BLAST SENT - CLAIMING PAID",
"FIELD VISIT RESULT - CLAIMING PAID",
"FV HAND CARRY - CLAIMING PAID",
"INBOUND CALL - CLAIMING PAID",
"INCOMING CALL - CLAIMING PAID",
"OUTBOUND CALL - CLAIMING PAID",
"OUTBOUND CALL_POSITIVE - CLAIMING PAID",
"OUTGOING CALL - CLAIMING PAID",
"POSITIVE CONTACT-CLAIMING PAID",
"SMS BLAST SENT - CLAIMING PAID",
"VIBER BLAST SENT - CLAIMING PAID",
"WITH FIELD RESULT - CLAIMING PAID"
)
AND debtor.`is_aborted` = 0
AND debtor.`is_locked` = 0

AND debtor_followup.claim_paid_date >= DATE_FORMAT(CURDATE() - INTERVAL 3 MONTH, '%Y-%m-01')
AND debtor_followup.claim_paid_date <  DATE_FORMAT(CURDATE() + INTERVAL 1 MONTH, '%Y-%m-01')

AND followup.datetime >= DATE_FORMAT(CURDATE() - INTERVAL 3 MONTH, '%Y-%m-01')
AND followup.datetime <  DATE_FORMAT(CURDATE() + INTERVAL 1 MONTH, '%Y-%m-01')

ORDER BY followup.`datetime` DESC;