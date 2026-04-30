begin;

DROP VIEW IF EXISTS v_matched_programs;
DROP VIEW IF EXISTS v_business_profile;

drop view if exists v_user_profile; 
CREATE OR REPLACE VIEW v_user_profile AS 
WITH latest_business AS ( 
  SELECT DISTINCT ON (b.profile_id) b.* 
  FROM public.businesses b 
  ORDER BY b.profile_id, b.created_at DESC 
), 
business_summary AS ( 
  SELECT b.id AS business_id, 
  b.profile_id AS user_id, 
  b.business_name, 
  b.registration_number, 
  b.registration_date, 
  b.tax_number, 
  b.business_type, 
  b.business_age_band, 
  b.employees_band, 
  b.website, 
  b.impact_focus, 
  EXTRACT(YEAR FROM AGE(CURRENT_DATE, b.registration_date))::integer AS years_in_business, 
  b.monthly_customers, 
  b.revenue_from_biggest_customer, 
  b.customer_payment_speed, 
  b.needs_matching,
  b.demographics,
  b.financial_documents
  FROM latest_business b 
), 
primary_industry AS ( 
  SELECT DISTINCT ON (business_id) business_id, 
  industry_name AS industry, 
  specialisation, 
  target_consumer, 
  seasonality, 
  is_export, 
  regulator 
  FROM public.business_industries 
  WHERE is_primary = true 
  ORDER BY business_id, created_at DESC 
), 
primary_location AS ( 
  SELECT DISTINCT ON (business_id) business_id, 
  province, 
  municipality, 
  postal_code, 
  type, 
  latitude, 
  longitude, 
  physical_address 
  FROM public.business_locations 
  WHERE is_primary = true 
  ORDER BY business_id, created_at DESC 
), 
owner_demographics AS ( 
  SELECT p.id AS user_id, 
  p.email, 
  u.email AS auth_email, 
  p.phone, 
  p.whatsapp_opt_in, 
  p.dob, 
  p.qualifications, 
  p.id_type, 
  p.id_number, 
  p.country AS owner_country, 
  p.province AS owner_province, 
  p.postal_code AS owner_postal_code, 
  p.full_name, 
  p.race, 
  p.gender, 
  CASE WHEN p.dob IS NOT NULL THEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.dob)) ELSE NULL END AS owner_age 
  FROM public.users p 
  JOIN auth.users u ON p.id = u.id 
), 
team_compliance_agg AS ( 
  SELECT DISTINCT ON (business_id) business_id, 
  team_size, 
  team_stage, 
  bbee_certification, 
  sars_status, 
  vat_status 
  FROM public.team_compliances 
  ORDER BY business_id, created_at DESC 
)
SELECT 
  od.user_id, 
  bs.business_id, 
  bs.business_name, 
  bs.registration_number, 
  bs.registration_date, 
  bs.tax_number, 
  bs.business_type, 
  bs.employees_band, 
  bs.monthly_customers, 
  bs.website, 
  bs.revenue_from_biggest_customer, 
  bs.customer_payment_speed, 
  bs.needs_matching, 
  bs.years_in_business, 
  bs.impact_focus,
  bs.demographics,
  bs.financial_documents,
  -- Industry 
  pi.industry, 
  pi.specialisation, 
  pi.seasonality, 
  pi.is_export, 
  pi.target_consumer, 
  pi.regulator, 
  -- Location 
  pl.province, 
  pl.municipality, 
  pl.postal_code, 
  pl.type, 
  pl.latitude, 
  pl.longitude, 
  pl.physical_address, 
  -- Compliance 
  tc.team_size, 
  tc.team_stage, 
  tc.sars_status, 
  tc.vat_status, 
  tc.bbee_certification, 
  -- Funding 
  fn.amount_min AS funding_amount_min, 
  fn.amount_max AS funding_amount_max, 
  fn.amount_exact AS funding_amount_exact, 
  fn.timeline_band, 
  fn.purposes AS funding_needs,
  fn.description AS funding_description, 
  -- Owner (PRIMARY DIMENSION NOW) 
  od.full_name, 
  od.id_type, 
  od.id_number, 
  od.dob, 
  od.owner_age, 
  od.gender, 
  od.race, 
  od.email, 
  od.auth_email, 
  od.phone, 
  od.whatsapp_opt_in, 
  od.qualifications, 
  od.owner_country, 
  od.owner_province, 
  od.owner_postal_code, 
  -- Financials 
  mf.type AS finance_type, 
  mf.bank_name, 
  mf.account_age, 
  mf.monthly_income_band, 
  mf.tracking_method, 
  -- Repayment 
  rpt.frequency AS repayment_frequency, 
  rpt.period AS repayment_period, 
  rpt.investors_share AS repayment_investor_share, 
  rpt.collateral AS repayment_collateral
FROM owner_demographics od 
LEFT JOIN business_summary bs ON od.user_id = bs.user_id 
LEFT JOIN primary_industry pi ON bs.business_id = pi.business_id 
LEFT JOIN primary_location pl ON bs.business_id = pl.business_id 
LEFT JOIN public.funding_needs fn ON bs.business_id = fn.business_id 
LEFT JOIN team_compliance_agg tc ON bs.business_id = tc.business_id 
LEFT JOIN public.financial_moneyflows mf ON bs.business_id = mf.business_id 
LEFT JOIN public.funding_repayment_terms rpt ON bs.business_id = rpt.business_id;

CREATE OR REPLACE VIEW v_business_profile AS
WITH business_summary AS (
  SELECT 
    b.id AS business_id,
    b.profile_id AS user_id,
    b.business_name,
    b.registration_number,
    b.registration_date,
    b.tax_number,
    b.business_type,
    b.business_age_band,
    b.employees_band,
    b.website,
    b.impact_focus,
    -- Calculate years in business from registration date
    EXTRACT(YEAR FROM AGE(CURRENT_DATE, b.registration_date))::integer AS years_in_business,
    b.monthly_customers,
    b.revenue_from_biggest_customer,
    b.customer_payment_speed,
    b.needs_matching,
    b.demographics,
    b.financial_documents
  FROM public.businesses b
),
primary_industry AS (
  SELECT DISTINCT ON (business_id) 
    business_id,
    industry_name AS industry,
    specialisation,
    target_consumer,
    seasonality,
    is_export,
    regulator
  FROM public.business_industries 
  WHERE is_primary = true
  ORDER BY business_id, created_at DESC
),
primary_location AS (
  SELECT DISTINCT ON (business_id) 
    business_id,
    province,
    municipality,
    postal_code,
    type,
    latitude,
    longitude,
    physical_address
  FROM public.business_locations 
  WHERE is_primary = true
  ORDER BY business_id, created_at DESC
),
owner_demographics AS (
  SELECT 
    p.id AS profile_id,
    p.email,
    u.email AS auth_email,
    p.phone,
    p.whatsapp_opt_in,
    p.dob,
    p.qualifications,
    p.id_type,
    p.id_number,
    p.country as owner_country,
    p.province as owner_province,
    p.postal_code as owner_postal_code,
    p.full_name AS owner_full_name,
    p.race,
    p.gender,
    CASE 
      WHEN p.dob IS NOT NULL THEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.dob))
      ELSE NULL
    END AS owner_age
  FROM public.users p
  JOIN auth.users u ON p.id = u.id
),
team_compliance_agg AS (
  SELECT 
    business_id,
    team_size,
    team_stage,
    bbee_certification,
    sars_status,
    vat_status
  FROM public.team_compliances
  ORDER BY created_at DESC
  LIMIT 1
)
SELECT 
  bs.business_id,
  bs.user_id,
  bs.business_name,
  bs.registration_number,
  bs.registration_date,
  bs.tax_number,
  bs.business_type,
  bs.employees_band,
  bs.monthly_customers,
  bs.website,
  bs.revenue_from_biggest_customer,
  bs.customer_payment_speed,
  bs.needs_matching,
  bs.years_in_business,
  bs.impact_focus,
  bs.demographics,
  bs.financial_documents,
  pi.industry,
  pi.specialisation,
  pi.seasonality,
  pi.is_export,
  pi.target_consumer,
  pi.regulator,
  pl.province,
  pl.municipality,
  pl.postal_code,
  pl.type,
  pl.latitude,
  pl.longitude,
  pl.physical_address,
  tc.team_size,
  tc.team_stage,
  tc.sars_status,
  tc.vat_status,
  tc.bbee_certification,
  fn.amount_min funding_amount_min,
  fn.amount_max funding_amount_max,
  fn.amount_exact funding_amount_exact,
  fn.timeline_band,
  fn.purposes funding_needs,
  fn.description funding_description,
  od.owner_full_name,
  od.id_type,
  od.id_number,
  od.dob,
  od.owner_age,
  od.gender,
  od.race,
  od.email,
  od.auth_email,
  od.phone,
  od.whatsapp_opt_in,
  od.qualifications,
  od.owner_country,
  od.owner_province,
  od.owner_postal_code,
  mf.type as finance_type,
  mf.bank_name,
  mf.account_age,
  mf.monthly_income_band,
  mf.tracking_method,
  rpt.frequency repayment_frequency,
  rpt.period repayment_period,
  rpt.investors_share repayment_investor_share,
  rpt.collateral repayment_collateral
FROM business_summary bs
LEFT JOIN primary_industry pi ON bs.business_id = pi.business_id
LEFT JOIN primary_location pl ON bs.business_id = pl.business_id
LEFT JOIN public.funding_needs fn ON bs.business_id = fn.business_id
LEFT JOIN owner_demographics od ON bs.user_id = od.profile_id
LEFT JOIN team_compliance_agg tc ON bs.business_id = tc.business_id
LEFT JOIN public.financial_moneyflows mf ON bs.business_id = mf.business_id
LEFT JOIN public.funding_repayment_terms rpt ON bs.business_id = rpt.business_id;


CREATE OR REPLACE VIEW v_matched_programs AS
SELECT 
  pm.id,
  pm.business_id,
  pm.program_id,
  pm.match_score,
  pm.eligibility_gaps,
  pm.match_reasons,
  pm.ai_analysis,
  pm.rule_score,
  pm.ai_score,
  pm.created_at,
  
  -- Business details
  bp.business_name,
  bp.industry,
  bp.business_type,
  bp.province,
  bp.employees_band,
  
  -- Program details
  p.program_name,
  p.funder_name as program_funder_name,
  p.program_id AS program_slug,
  p.funding_lines AS program_funding_lines,
  p.raw_eligibility_data AS program_eligibility,
  p.ticket_min AS program_funding_amount_min,
  p.ticket_max AS program_funding_amount_max,
  p.currency AS program_funding_currency,
  p.industries AS program_sectors,
  p.source_domain AS program_source,
  p.source_url AS program_url,
  p.ownership_targets AS program_ethnicity_requirement,
  p.deadline_type as program_deadline_type,
  p.deadline_date as program_deadline_date,
  p.application_channel as program_application_channel,
  p.application_url as program_application_url,
  p.created_at AS program_created_at,
  
  -- Match category based on score
  CASE 
    WHEN pm.match_score >= 80 THEN 'Excellent'
    WHEN pm.match_score >= 60 THEN 'Good'
    WHEN pm.match_score >= 40 THEN 'Potential'
    ELSE 'Weak'
  END AS match_category,
  
  -- Match confidence
  CASE 
    WHEN pm.ai_score > 0 AND pm.ai_score >= pm.rule_score THEN 'AI-High'
    WHEN pm.ai_score > 0 THEN 'AI-Medium'
    WHEN pm.rule_score >= 70 THEN 'Rule-High'
    WHEN pm.rule_score >= 50 THEN 'Rule-Medium'
    ELSE 'Rule-Low'
  END AS match_confidence

FROM public.program_matches pm
JOIN v_business_profile bp ON pm.business_id = bp.business_id
JOIN public.funding_programmes p ON pm.program_id = p.program_id
ORDER BY pm.match_score DESC, pm.created_at DESC;

commit;