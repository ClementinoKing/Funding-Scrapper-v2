import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Field, FieldLabel, FieldDescription } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Building2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { UserProfileView } from "@/types/api";

export default function BusinessTrading({
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
          <Building2 className="h-5 w-5" />
          Business & Trading
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label htmlFor="monthlyCustomers">Customers served monthly</Label>
            <Select
              defaultValue={profile?.monthly_customers}
              value={profile?.monthly_customers}
              onValueChange={(value) =>
                setProfile({ ...profile, monthly_customers: value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1-10">1-10 customers</SelectItem>
                <SelectItem value="11-50">11-50 customers</SelectItem>
                <SelectItem value="51-100">51-100 customers</SelectItem>
                <SelectItem value="100+">100+ customers</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="biggestCustomerRevenue">
              Revenue from biggest customer
            </Label>
            <Select
              defaultValue={profile?.revenue_from_biggest_customer}
              value={profile?.revenue_from_biggest_customer}
              onValueChange={(value) =>
                setProfile({ ...profile, revenue_from_biggest_customer: value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select percentage" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0-10">0-10%</SelectItem>
                <SelectItem value="11-25">11-25%</SelectItem>
                <SelectItem value="26-50">26-50%</SelectItem>
                <SelectItem value="50+">50%+</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="paymentTerms">Payment period from customers</Label>
            <Select
              defaultValue={profile?.customer_payment_speed}
              value={profile?.customer_payment_speed}
              onValueChange={(value) =>
                setProfile({ ...profile, customer_payment_speed: value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select timeframe" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="immediate">Immediate</SelectItem>
                <SelectItem value="7-days">7 days</SelectItem>
                <SelectItem value="30-days">30 days</SelectItem>
                <SelectItem value="60-days">60 days</SelectItem>
                <SelectItem value="90+">90+ days</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <Field className="hidden">
          <FieldLabel>How do customers pay you?</FieldLabel>
          <FieldDescription>
            Choose all that apply. Add detail for better matches.
          </FieldDescription>
          <div className="flex flex-wrap gap-2 mt-2">
            {[
              "Card",
              "Cash",
              "Mobile / App / QR",
              "Debit Orders",
              "Instant EFT / Pay-by-link",
              "EFT / Bank Transfer",
            ].map((method) => (
              <Badge
                key={method}
                // variant={
                //   formData.paymentMethods.find(p => p.payment_name === method) ? "default" : "outline"
                // }
                variant="outline"
                className="cursor-pointer gap-1 p-1.5"
                // onClick={() => addMethod(method)}
              >
                {method}
                {/* {formData.paymentMethods.find(p => p.payment_name === method) && (
                    <X className="w-3 h-3" />
                  )} */}
              </Badge>
            ))}
          </div>
        </Field>
      </CardContent>
    </Card>
  );
}
