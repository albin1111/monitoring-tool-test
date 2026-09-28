SELECT
    followup.datetime AS 'DISPO DATE',
    DATE_FORMAT(followup.datetime, '%m/%d/%Y') AS 'Action Date',
    debtor.account AS 'Account No',
    debtor.assign_date AS 'Endorsement Date',
    debtor.name AS 'Debtor',
    debtor.balance AS 'Balance',
    debtor.old_ic AS 'Old IC',
    followup.status_code AS 'Status',
    followup.remark AS 'Remark',
    followup.created_at AS 'Remark Date',
    debtor_followup.ptp_amount AS 'PTP Amount',
    debtor_followup.ptp_date AS 'PTP Date',
    debtor_followup.claim_paid_amount AS 'Claim Paid Amount',
    debtor_followup.claim_paid_date AS 'Claim Paid Date',
    debtor.placement AS 'Placement',
    debtor_followup.created_by AS 'Remark By',
    debtor.client_name AS 'CAMPAIGN'
FROM debtor_followup
INNER JOIN debtor
    ON debtor.id = debtor_followup.debtor_id
INNER JOIN followup
    ON followup.id = debtor_followup.followup_id
WHERE debtor.client_name = ?
    AND debtor.is_aborted = 0
    AND debtor.is_locked = 0
    AND debtor_followup.created_at >= ?
    AND debtor_followup.created_at < DATE_ADD(?, INTERVAL 1 DAY)
    AND (
        followup.status_code LIKE '%PTP%'
        OR followup.status_code LIKE '%KEPT%'
    )
ORDER BY debtor_followup.created_at DESC;