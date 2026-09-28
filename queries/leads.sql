WITH ranked_contacts AS (
    SELECT
        cn.debtor_id,
        cn.contact_number,
        ROW_NUMBER() OVER (
            PARTITION BY cn.debtor_id
            ORDER BY cn.id
        ) AS rn
    FROM contact_number cn
    JOIN contact_number_type cnt
        ON cnt.id = cn.contact_number_type_id
    WHERE cnt.name = 'Mobile'
)

SELECT
    debtor.`account`,
    debtor.`card_no`,
    debtor.`name`,
    debtor.`old_ic`,

    MAX(CASE WHEN rc.rn = 1 THEN rc.contact_number END) AS phone_1,
    MAX(CASE WHEN rc.rn = 2 THEN rc.contact_number END) AS phone_2,
    MAX(CASE WHEN rc.rn = 3 THEN rc.contact_number END) AS phone_3,

    CASE
        WHEN debtor.`product_type` IN ('MAD IMPACTED', 'NO CONTACT', 'NON-COMPLYING PA')
            THEN 'CARDS'
        ELSE debtor.`product_type`
    END AS Product,

    debtor.`placement`,
    debtor.`product_group`,
    debtor.`balance`,
    debtor.`assign_date`,
    debtor.`expiry_date`,
    debtor.`date_of_birth`,
    debtor.`debtor_email`

FROM debtor
LEFT JOIN ranked_contacts rc
    ON rc.debtor_id = debtor.id

WHERE debtor.`client_id` IN (75, 77, 81)
  AND debtor.`is_aborted` = 0
  AND debtor.`is_locked` = 0

GROUP BY
    debtor.`account`,
    debtor.`card_no`,
    debtor.`name`,
    debtor.`old_ic`,

    CASE
        WHEN debtor.`product_type` IN ('MAD IMPACTED', 'NO CONTACT', 'NON-COMPLYING PA')
            THEN 'CARDS'
        ELSE debtor.`product_type`
    END,

    debtor.`placement`,
    debtor.`product_group`,
    debtor.`balance`,
    debtor.`assign_date`,
    debtor.`expiry_date`,
    debtor.`date_of_birth`,
    debtor.`debtor_email`

ORDER BY debtor.`assign_date` ASC;