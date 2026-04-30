begin;

ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_industries ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_compliance ENABLE ROW LEVEL SECURITY;
ALTER TABLE funding_needs ENABLE ROW LEVEL SECURITY;
ALTER TABLE funding_need_purposes ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_moneyflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_compliances ENABLE ROW LEVEL SECURITY;
ALTER TABLE demographics ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE funding_repayment_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE funding_purposes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own businesses"
ON businesses
FOR ALL
USING (profile_id = auth.uid())
WITH CHECK (profile_id = auth.uid());

CREATE POLICY "Users manage own business_locations"
ON business_locations
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = business_locations.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = business_locations.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own business_industries"
ON business_industries
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = business_industries.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = business_industries.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own business_compliance"
ON business_compliance
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = business_compliance.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = business_compliance.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own funding_needs"
ON funding_needs
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = funding_needs.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = funding_needs.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own funding_need_purposes"
ON funding_need_purposes
FOR ALL
USING (
  EXISTS (
    SELECT 1
    FROM funding_needs fn
    JOIN businesses b ON b.id = fn.business_id
    WHERE fn.id = funding_need_purposes.funding_need_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM funding_needs fn
    JOIN businesses b ON b.id = fn.business_id
    WHERE fn.id = funding_need_purposes.funding_need_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own payment_types"
ON payment_types
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = payment_types.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = payment_types.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own financial_moneyflows"
ON financial_moneyflows
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = financial_moneyflows.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = financial_moneyflows.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own team_compliances"
ON team_compliances
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = team_compliances.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = team_compliances.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own demographics"
ON demographics
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = demographics.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = demographics.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own financial_documents"
ON financial_documents
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = financial_documents.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = financial_documents.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users manage own funding_repayment_terms"
ON funding_repayment_terms
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = funding_repayment_terms.business_id
    AND b.profile_id = auth.uid()
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = funding_repayment_terms.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Users read own program_matches"
ON program_matches
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM businesses b
    WHERE b.id = program_matches.business_id
    AND b.profile_id = auth.uid()
  )
);

CREATE POLICY "Authenticated users can read funding_purposes"
ON funding_purposes
FOR SELECT
USING (auth.uid() IS NOT NULL);

commit;