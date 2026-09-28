SELECT
    followup.id AS 'FOLLOWUP ID',
    debtor.account AS 'ACCOUNT',
    debtor.placement AS 'LEVEL',
    debtor.product_type AS 'PRODUCT TYPE',
    followup.status_code AS 'STATUS CODE',
    followup.remark AS 'REMARK',
    followup.contact_number AS 'CONTACT NUMBER',
    CASE
        WHEN debtor_followup.claim_paid_amount > 0 THEN debtor_followup.claim_paid_amount 
        WHEN debtor_followup.ptp_amount > 0 THEN debtor_followup.ptp_amount 
        ELSE NULL 
    END AS 'PAYMENT AMOUNT',
    CASE
        WHEN debtor_followup.claim_paid_amount > 0 THEN debtor_followup.claim_paid_date
        WHEN debtor_followup.ptp_amount > 0 THEN debtor_followup.ptp_date
        ELSE NULL 
    END AS 'PAYMENT DATE',
    followup.datetime AS 'DISPO DATE'
FROM debtor
LEFT JOIN debtor_followup
    ON debtor_followup.debtor_id = debtor.id
LEFT JOIN followup
    ON followup.id = debtor_followup.followup_id
WHERE debtor.client_name IN ('SBC CARDS RECOV L1', 'SBC CARDS & LOAN L6', 'SBC PL RECOV L1')
    # AND 1 = 1
    AND followup.date = '2026-02-25'
    AND NOT (
        followup.remark LIKE '%Updates when case reassign%' OR
        followup.remark LIKE '%New Contact Details Added%' OR
        followup.remark LIKE '%New Assignment - OS%' OR
        followup.remark LIKE '%Broken Promise%' OR
        followup.remark LIKE '%New files imported%')