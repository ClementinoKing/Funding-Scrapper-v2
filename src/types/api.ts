export interface UserProfileView {
  // Core identifiers
  user_id: string;
  business_id?: string;

  // Business
  business_name?: string;
  registration_number?: string;
  registration_date?: string; // ISO date
  tax_number?: string;
  business_type?: string;
  employees_band?: string;
  monthly_customers?: string;
  website?: string;
  revenue_from_biggest_customer?: string;
  business_age_band?: string;
  customer_payment_speed?: string;
  needs_matching: boolean | null;
  years_in_business?: number;
  impact_focus?: string;
  demographics?: string | string[];
  financial_documents?: string | string[];
  funding_needs?: string | string[];

  // Industry
  industry?: string;
  specialisation?: string;
  seasonality?: string;
  is_export: boolean | null;
  target_consumer?: string;
  regulator?: string;

  // Location
  province?: string;
  municipality?: string;
  postal_code?: string;
  type?: string;
  latitude?: number;
  longitude?: number;
  physical_address?: string;

  // Compliance
  team_size?: string;
  team_stage?: string;
  sars_status?: string;
  vat_status?: string;
  bbee_certification?: string;

  // Funding
  funding_amount_min?: number;
  funding_amount_max?: number;
  funding_amount_exact?: number;
  timeline_band?: string;
  funding_description?: string;

  // Owner (primary dimension)
  full_name?: string;
  id_type?: string;
  id_number?: string;
  dob?: string; // ISO date
  owner_age?: number;
  gender?: string;
  race?: string;
  email?: string;
  auth_email?: string;
  phone?: string;
  whatsapp_opt_in: boolean | null;
  qualifications?: string;
  owner_country?: string;
  owner_province?: string;
  owner_postal_code?: string;
  profile_completeness?: number;

  // Financials
  finance_type?: string;
  bank_name?: string;
  account_age?: string;
  monthly_income_band?: string;
  tracking_method?: string;

  // Repayment
  repayment_frequency?: string;
  repayment_period?: string;
  repayment_investor_share?: string;
  repayment_collateral?: string;

  // Funding purposes
  funding_purposes_string?: string;
  funding_purposes_array?: string[];
}