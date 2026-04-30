import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { User, IdCard } from "lucide-react";
import { PROVINCES } from "@/constants/profile";
import { UserProfileView } from "@/types/api";

export default function PersonalDetails({
  profile,
  setProfile,
}: {
  profile: UserProfileView;
  setProfile: (profile: UserProfileView) => void;
}) {
  console.log(profile);
  return (
    <>
      {/* Personal Information */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Personal Information
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="ownerFullName">Owner Full Name</Label>
            <Input
              id="ownerFullName"
              value={profile?.full_name || ""}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  full_name: e.target.value,
                })
              }
              placeholder="Enter your full name"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={profile?.email || profile?.auth_email || ""}
                disabled
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                value={profile?.phone || ""}
                onChange={(e) =>
                  setProfile({ ...profile, phone: e.target.value })
                }
                placeholder="+27 12 345 6789"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="dob">Date of Birth</Label>
              <Input
                id="dob"
                type="date"
                value={profile?.dob ? profile?.dob.split("T")[0] : ""}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    dob: e.target.value || undefined,
                  })
                }
                max={new Date().toISOString().split("T")[0]}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="qualification">Highest Qualification</Label>
              <Input
                id="qualification"
                type="text"
                value={profile?.qualifications || ""}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    qualifications: e.target.value || undefined,
                  })
                }
                placeholder="Enter your highest qualification"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Identification & Location */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IdCard className="h-5 w-5" />
            Identification & Location
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="id_type">ID Type</Label>
              <Select
                defaultValue={profile?.id_type}
                value={profile?.id_type}
                onValueChange={(value) =>
                  setProfile({ ...profile, id_type: value })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select an ID Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sa-id">SA ID</SelectItem>
                  <SelectItem value="passport">Passport</SelectItem>
                  <SelectItem value="asylum-seeker-permit">
                    Asylum Seeker Permit
                  </SelectItem>
                  <SelectItem value="work-permit">Work Permit</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="id_number">ID Number</Label>
              <Input
                id="id_number"
                type="tel"
                value={profile?.id_number || ""}
                onChange={(e) =>
                  setProfile({ ...profile, id_number: e.target.value })
                }
                placeholder="e.g. 1234567890123"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="gender">Gender</Label>
              <Select
                defaultValue={profile?.gender}
                value={profile?.gender}
                onValueChange={(value) =>
                  setProfile({ ...profile, gender: value })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a gender" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="male">Male</SelectItem>
                  <SelectItem value="female">Female</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                  <SelectItem value="rather-not-say">Rather not say</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="owner_country">Country</Label>
              <Select
                defaultValue={profile?.owner_country}
                value={profile?.owner_country}
                onValueChange={(value) =>
                  setProfile({ ...profile, owner_country: value })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a country" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="south-africa">South Africa</SelectItem>
                  <SelectItem value="botswana">Botswana</SelectItem>
                  <SelectItem value="eswatini">Eswatini</SelectItem>
                  <SelectItem value="lesotho">Lesotho</SelectItem>
                  <SelectItem value="zimbabwe">Zimbabwe</SelectItem>
                  <SelectItem value="mozambique">Mozambique</SelectItem>
                  <SelectItem value="zambia">Zambia</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="owner_province">Province</Label>
              <Select
                defaultValue={profile?.owner_province}
                value={profile?.owner_province}
                onValueChange={(value) =>
                  setProfile({ ...profile, owner_province: value })
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
              <Label htmlFor="owner-postal-code">Postal Code</Label>
              <Input
                id="owner-postal-code"
                type="text"
                value={profile?.owner_postal_code || ""}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    owner_postal_code: e.target.value || undefined,
                  })
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
