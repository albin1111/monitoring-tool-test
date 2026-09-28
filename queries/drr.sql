SELECT
    followup.datetime AS 'DISPO DATE',
    DATE_FORMAT(followup.datetime, '%m/%d/%Y') AS 'Action Date',
    debtor.account AS 'Account No',
    debtor.assign_date AS 'Endorsement Date',
    debtor.name AS 'Debtor',
    debtor.balance AS 'Balance',
    debtor.days_past_due AS 'DPD',
    debtor.card_no AS 'Card No',
    debtor.old_ic AS 'Old IC',
    followup.status_code AS 'Status',
    followup.remark AS 'Remark',
    followup.created_at AS 'Remark Date',
    debtor_followup.ptp_amount AS 'PTP Amount',
    debtor_followup.ptp_date AS 'PTP Date',
    debtor_followup.claim_paid_amount AS 'Claim Paid Amount',
    debtor_followup.claim_paid_date AS 'Claim Paid Date',
    debtor.placement AS 'Placement',
    debtor.cycle AS 'Cycle',
    debtor.product_type AS 'Product Type',
    debtor.collector_user_name AS 'Collector',
    user.name AS 'Agency Agent Name',
    debtor_followup.created_by AS 'Remark By',
    followup.contact_number AS 'Dialed Number',
    contact_number_type.`name` AS 'Contact Type',
    debtor.client_name AS 'CAMPAIGN'
FROM debtor
LEFT JOIN debtor_followup
    ON debtor_followup.debtor_id = debtor.id
LEFT JOIN followup
    ON followup.id = debtor_followup.followup_id
LEFT JOIN `user`
    ON `user`.id = followup.remark_by_id
LEFT JOIN `contact_number`
    ON contact_number.`id` = followup.`contact_number_id`
LEFT JOIN `contact_number_type`
    ON contact_number_type.`id` = contact_number.`contact_number_type_id`
WHERE debtor.client_name = ?
    AND followup.date BETWEEN ? AND ?
    AND NOT (
        followup.remark LIKE '%Updates when case reassign%' OR
        followup.remark LIKE '%New Contact Details Added%' OR
        followup.remark LIKE '%New Assignment - OS%' OR
        followup.remark LIKE '%Broken Promise%' OR
        followup.remark LIKE '%New files imported%'
    )