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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import {
  Building2,
  CheckCircle2,
} from "lucide-react";
import {
  BUSINESS_TYPES,
  PROVINCES,
  INDUSTRIES,
} from "@/constants/profile";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { UserProfileView } from "@/types/api";

export default function BusinessDetail({
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
          Business Information
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="businessName">Business Name</Label>
          <Input
            id="businessName"
            value={profile?.business_name || ""}
            onChange={(e) =>
              setProfile({
                ...profile,
                business_name: e.target.value,
              })
            }
            placeholder="Business name"
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="businessType">Business Type</Label>
            <Select
              defaultValue={profile?.business_type}
              value={profile?.business_type}
              onValueChange={(value) =>
                setProfile({ ...profile, business_type: value })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a business type" />
              </SelectTrigger>
              <SelectContent>
                  {BUSINESS_TYPES.map((type) => (
                    <SelectItem id={type.id} value={type.id}>
                      <div className="flex items-center gap-2">
                        <type.icon className={cn("w-4 h-4", type.color)} />
                        <div>
                          <p className="text-sm font-medium">{type.label}</p>
                          <p className="text-xs text-muted-foreground">
                            {type.description}
                          </p>
                        </div>
                      </div>
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="industry">Industry</Label>
            <Select
              defaultValue={profile?.industry}
              value={profile?.industry}
              onValueChange={(value) =>
                setProfile({ ...profile, industry: value })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select an industry" />
              </SelectTrigger>
              <SelectContent>
                  {INDUSTRIES.map((industry) => (
                    <SelectItem key={industry} value={industry}>
                      {industry}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="companyRegistrationNumber">
              Company Registration Number
            </Label>
            <Input
              id="companyRegistrationNumber"
              value={profile?.registration_number || ""}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  registration_number: e.target.value,
                })
              }
              placeholder="CIPC registration number"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="registrationDate">
              Registration Date
            </Label>
            <Input
              id="registrationDate"
              type="date"
              value={profile?.registration_date ? profile?.registration_date.split("T")[0] : ""}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  registration_date: e.target.value || undefined,
                })
              }
              max={new Date().toISOString().split("T")[0]}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="province">Province</Label>
            <Select
              defaultValue={profile?.province}
              value={profile?.province}
              onValueChange={(value) =>
                setProfile({ ...profile, province: value })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a province" />
              </SelectTrigger>
              <SelectContent>
                  {PROVINCES.map((province) => (
                    <SelectItem key={province} value={province}>
                      {province}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="postal-code">Postal Code</Label>
            <Input
              id="postal-code"
              type="text"
              value={profile?.postal_code || ""}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  postal_code: e.target.value || undefined,
                })
              }
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="physicalAddress">Physical Address</Label>
          <Textarea
            id="physicalAddress"
            value={profile?.physical_address || ""}
            onChange={(e) =>
              setProfile({
                ...profile,
                physical_address: e.target.value || undefined,
              })
            }
            placeholder="Physical address"
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="website">Website</Label>
            <Input
              id="website"
              type="url"
              value={profile?.website || ""}
              onChange={(e) =>
                setProfile({ ...profile, website: e.target.value })
              }
              placeholder="https://www.example.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="taxNumber">Tax Number</Label>
            <Input
              id="taxNumber"
              value={profile?.tax_number || ""}
              onChange={(e) =>
                setProfile({ ...profile, tax_number: e.target.value })
              }
              placeholder="Tax number"
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5 flex-1">
            <Label htmlFor="emailNotifications">Do you export?</Label>
            <p className="text-sm text-muted-foreground">
              Sell products/services outside South Africa
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={profile?.is_export || false}
              onChange={(e) => setProfile({ ...profile, is_export: e.target.checked })}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
          </label>
        </div>

        <div className="space-y-0.5 flex-1">
          <Label>How seasonal is your business?</Label>
        </div>
        <div className="grid grid-cols-4 gap-2 md:gap-4">
          {["none", "low", "medium", "high"].map((option) => (
            <button
              onClick={() => setProfile({ ...profile, seasonality: option })}
              className={cn(
                "p-2 rounded-lg border-2 text-left transition-all",
                profile?.seasonality?.toLowerCase() === option
                  ? "border-primary bg-primary-foreground dark:bg-primary/20"
                  : "border-border hover:border-primary",
                "flex justify-between items-start text-xs md:text-sm",
              )}
            >
              <h3 className="font-semibold">{option.charAt(0).toUpperCase() + option.slice(1)}</h3>
              {profile?.seasonality === option && (
                <CheckCircle2 className="w-5 h-5 text-primary" />
              )}
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
