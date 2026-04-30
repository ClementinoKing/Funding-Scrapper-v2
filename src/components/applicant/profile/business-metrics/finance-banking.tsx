import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Field, FieldLabel, FieldDescription } from "@/components/ui/field";
import {
  Building2,
  DollarSign,
  CheckCircle2,
  Banknote,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { UserProfileView } from "@/types/api";

export default function FinanceBanking({
  profile,
  setProfile,
}: {
  profile: UserProfileView;
  setProfile: (profile: UserProfileView) => void;
}) {
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DollarSign className="h-5 w-5" />
          Finance & Banking
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <FieldLabel className="mb-4 block">
            Where does your money go?
          </FieldLabel>
          <FieldDescription className="mb-4">
            This helps match you with suitable funders
          </FieldDescription>
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setProfile({ ...profile, finance_type: "bank" })}
              className={cn(
                "p-6 rounded-lg border-2 text-left transition-all",
                profile?.finance_type === "bank"
                  ? "border-primary bg-primary-foreground dark:bg-primary/20"
                  : "border-border hover:border-primary",
              )}
            >
              <div className="flex justify-between items-start mb-2">
                <Building2 className="w-8 h-8 text-primary" />
                {profile?.finance_type === "bank" && (
                  <CheckCircle2 className="w-5 h-5 text-primary" />
                )}
              </div>
              <h3 className="font-semibold">I bank my money</h3>
            </button>
            <button
              onClick={() => setProfile({ ...profile, finance_type: "cash" })}
              className={cn(
                "p-6 rounded-lg border-2 text-left transition-all",
                profile?.finance_type === "cash"
                  ? "border-primary bg-primary-foreground dark:bg-primary/20"
                  : "border-border hover:border-primary",
              )}
            >
              <div className="flex justify-between items-start mb-2">
                <Banknote className="w-8 h-8 text-primary mb-2" />
                {profile?.finance_type === "cash" && (
                  <CheckCircle2 className="w-5 h-5 text-primary" />
                )}
              </div>
              <h3 className="font-semibold">Mostly cash-based</h3>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field>
            <FieldLabel>Which bank do you use?</FieldLabel>
            <Select
              defaultValue={profile?.bank_name}
              value={profile?.bank_name}
              onValueChange={(value) => setProfile({ ...profile, bank_name: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select bank" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="fnb">FNB</SelectItem>
                <SelectItem value="absa">Absa</SelectItem>
                <SelectItem value="nedbank">Nedbank</SelectItem>
                <SelectItem value="standard-bank">Standard Bank</SelectItem>
                <SelectItem value="capitec">Capitec</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
          </Field>

          <Field>
            <FieldLabel>How long have you had this account?</FieldLabel>
            <Select
              defaultValue={profile?.account_age}
              value={profile?.account_age}
              onValueChange={(value) => setProfile({ ...profile, account_age: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select duration" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="less-than-1">Less than 1 year</SelectItem>
                <SelectItem value="1-2-years">1-2 years</SelectItem>
                <SelectItem value="3-5-years">3-5 years</SelectItem>
                <SelectItem value="more-than-5">More than 5 years</SelectItem>
              </SelectContent>
            </Select>
          </Field>

          <Field>
            <FieldLabel>What's your monthly income/revenue?</FieldLabel>
            <Select
              defaultValue={profile?.monthly_income_band}
              value={profile?.monthly_income_band}
              onValueChange={(value) => setProfile({ ...profile, monthly_income_band: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="under-10k">Under R10,000</SelectItem>
                <SelectItem value="10k-25k">R10,000 - R25,000</SelectItem>
                <SelectItem value="25k-50k">R25,000 - R50,000</SelectItem>
                <SelectItem value="50k-100k">R50,000 - R100,000</SelectItem>
                <SelectItem value="100k-250k">R100,000 - R250,000</SelectItem>
                <SelectItem value="250k-500k">R250,000 - R500,000</SelectItem>
                <SelectItem value="500k+">R500,000+</SelectItem>
              </SelectContent>
            </Select>
          </Field>

          <Field>
            <FieldLabel>How do you track your finances?</FieldLabel>
            <Select
              defaultValue={profile?.tracking_method}
              value={profile?.tracking_method}
              onValueChange={(value) => setProfile({ ...profile, tracking_method: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select method" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="excel">Excel or Google Sheets</SelectItem>
                <SelectItem value="accounting-software">
                  Accounting software (Xero, QuickBooks, etc.)
                </SelectItem>
                <SelectItem value="bank-statements">
                  Bank statements only
                </SelectItem>
                <SelectItem value="accountant">
                  Accountant/bookkeeper
                </SelectItem>
                <SelectItem value="none">I don't track</SelectItem>
              </SelectContent>
            </Select>
          </Field>
        </div>
      </CardContent>
    </Card>
  );
}
