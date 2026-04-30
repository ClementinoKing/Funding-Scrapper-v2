import { supabase } from "@/lib/supabase";
import { UserProfileView } from "@/types/api";

export async function savePersonalDetails(profile: UserProfileView) {
  const { error } = await supabase
    .from("users")
    .update({
      phone: profile.phone,
      whatsapp_opt_in: profile.whatsapp_opt_in,
      dob: profile.dob,
      qualifications: profile.qualifications,
      id_type: profile.id_type,
      id_number: profile.id_number,
      country: profile.owner_country,
      province: profile.owner_province,
      postal_code: profile.owner_postal_code,
      full_name: profile.full_name,
      race: profile.race,
      gender: profile.gender,
    })
    .eq("id", profile.user_id);
  if (error) {
    console.error("Error saving personal details:", error);
  }
  return true;
}

export async function saveBusinessDetails(profile: UserProfileView) {
    const { error } = await supabase
        .from("businesses")
        .update({
            business_name: profile.business_name,
            registration_number: profile.registration_number,
            registration_date: profile.registration_date,
            tax_number: profile.tax_number,
            business_type: profile.business_type,
            business_age_band: profile?.business_age_band,
            employees_band: profile?.employees_band,
            website: profile?.website,
            impact_focus: profile?.impact_focus,
            monthly_customers: profile?.monthly_customers,
            revenue_from_biggest_customer: profile?.revenue_from_biggest_customer,
            customer_payment_speed: profile?.customer_payment_speed,
            demographics: profile?.demographics,
            financial_documents: profile?.financial_documents,
        })
        .eq("id", profile.business_id);

    const {data: existingIndustries} = await supabase
        .from("business_industries")
        .select("*")
        .eq("business_id", profile.business_id)
        .eq("is_primary", true);

    if (existingIndustries && existingIndustries?.length > 0) {
        await supabase
            .from("business_industries")
            .update({
                industry_name: profile.industry,
                specialisation: profile.specialisation,
                target_consumer: profile.target_consumer,
                regulator: profile.regulator,
                seasonality: profile.seasonality,
                is_export: profile.is_export,
                business_id: profile.business_id,
            })
            .eq("business_id", profile.business_id)
            .eq("is_primary", true);
    } else {
        await supabase
            .from("business_industries")
            .insert({
                industry_name: profile.industry,
                specialisation: profile.specialisation,
                target_consumer: profile.target_consumer,
                regulator: profile.regulator,
                seasonality: profile.seasonality,
                is_export: profile.is_export,
                business_id: profile.business_id,
                is_primary: true,
            });
    }

    const {data: existingLocations} = await supabase
        .from("business_locations")
        .select("*")
        .eq("business_id", profile.business_id)
        .eq("is_primary", true);

    if(existingLocations && existingLocations.length > 0) {
        await supabase
            .from("business_locations")
            .update({
                province: profile.province,
                municipality: profile.municipality,
                postal_code: profile.postal_code,
                latitude: profile.latitude,
                longitude: profile.longitude,
                physical_address: profile.physical_address,
                business_id: profile.business_id,
            })
            .eq("business_id", profile.business_id)
            .eq("is_primary", true);
    } else {
        await supabase
            .from("business_locations")
            .insert({
                province: profile.province,
                municipality: profile.municipality,
                postal_code: profile.postal_code,
                latitude: profile.latitude,
                longitude: profile.longitude,
                physical_address: profile.physical_address,
                business_id: profile.business_id,
                is_primary: true,
            });
    }
    if (error) {
        console.error("Error saving business details:", error);
    }
    return true;
}

export async function saveBusinessMetrics(profile: UserProfileView) {
    const {data: existingTeam} = await supabase
    .from("team_compliances")
    .select("*")
    .eq("business_id", profile.business_id);

    if(existingTeam && existingTeam?.length > 0) {
        await supabase
            .from("team_compliances")
            .update({
                team_size: profile.team_size,
                team_stage: profile.team_stage,
                sars_status: profile.sars_status,
                vat_status: profile.vat_status,
                bbee_certification: profile.bbee_certification,
            })
            .eq("business_id", profile.business_id);
    }else {
        await supabase
            .from("team_compliances")
            .insert({
                business_id: profile.business_id,
                team_size: profile.team_size,
                team_stage: profile.team_stage,
                sars_status: profile.sars_status,
                vat_status: profile.vat_status,
                bbee_certification: profile.bbee_certification,
            });    
    }

    const {data: existingFlows} = await supabase
    .from("financial_moneyflows")
    .select("*")
    .eq("business_id", profile.business_id);

    if(existingFlows && existingFlows?.length > 0) {
        await supabase
        .from("financial_moneyflows")
        .update({
            type: profile?.finance_type,
            bank_name: profile?.bank_name,
            account_age: profile?.account_age,
            monthly_income_band: profile?.monthly_income_band,
            tracking_method: profile?.tracking_method
        })
        .eq("business_id", profile.business_id);
    } else {
        await supabase
        .from("financial_moneyflows")
        .insert({
            business_id: profile.business_id,
            type: profile?.finance_type,
            bank_name: profile?.bank_name,
            account_age: profile?.account_age,
            monthly_income_band: profile?.monthly_income_band,
            tracking_method: profile?.tracking_method
        });
    }

    // TODO: Add payment types

    return true;
}


export async function saveFundingRequirements(profile: UserProfileView) {
    const {data: existingFundingNeeds} = await supabase
    .from("funding_needs")
    .select("*")
    .eq("business_id", profile.business_id);

    if(existingFundingNeeds && existingFundingNeeds?.length > 0) {
        await supabase
        .from("funding_needs")
        .update({
            amount_min: profile.funding_amount_min,
            amount_max: profile.funding_amount_max,
            amount_exact: profile.funding_amount_exact,
            timeline_band: profile.timeline_band,
            purposes: profile?.funding_needs,
            description: profile.funding_description,
            amount_mode: "range",
        })
        .eq("business_id", profile.business_id);
    } else {
        await supabase
        .from("funding_needs")
        .insert({
            business_id: profile.business_id,
            amount_min: profile.funding_amount_min,
            amount_max: profile.funding_amount_max,
            amount_exact: profile.funding_amount_exact,
            timeline_band: profile.timeline_band,
            purposes: profile?.funding_needs,
            description: profile.funding_description,
            amount_mode: "range",
        });
    }

    const {data: existingFundingRepaymentTerms} = await supabase
    .from("funding_repayment_terms")
    .select("*")
    .eq("business_id", profile.business_id);

    if(existingFundingRepaymentTerms && existingFundingRepaymentTerms?.length > 0) {
        await supabase
        .from("funding_repayment_terms")
        .update({
            frequency: profile.repayment_frequency,
            period: profile.repayment_period,
            investors_share: profile.repayment_investor_share,
            collateral: profile.repayment_collateral
        })
        .eq("business_id", profile.business_id)
        .throwOnError();
    } else {
        await supabase
        .from("funding_repayment_terms")
        .insert({
            business_id: profile.business_id,
            frequency: profile.repayment_frequency,
            period: profile.repayment_period,
            investors_share: profile.repayment_investor_share,
            collateral: profile.repayment_collateral
        })
        .throwOnError();
    }

    // TODO: Add funding purposes
    
    return true;
}