SELECT
    debtor.`account` AS 'Account No',
    debtor.`card_no` AS 'Card No',
    debtor.`name` AS 'Debtor',
    debtor.`old_ic` AS 'Old IC',
    debtor.`placement` AS 'Placement',
    debtor.`product_group` AS 'Product Group',
    debtor.`balance` AS 'Balance',
    debtor.`assign_date` AS 'Endorsement Date',
    debtor.`expiry_date` AS 'Expiry Date',
    debtor.`date_of_birth` AS 'Date of Birth',
    debtor.`debtor_email` AS 'Email',
    debtor.`client_name` AS 'Client Name'

FROM debtor

WHERE debtor.`client_name` = ?
  AND debtor.`is_aborted` = 0
  AND debtor.`is_locked` = 0

ORDER BY debtor.`assign_date` ASC;