import { useQuery } from "@tanstack/react-query";
import { SectionHeader } from "@/components/shared/section-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/services/api/client";

export function ApplicantProfilePage() {
  const { data: profile } = useQuery({
    queryKey: ["profile"],
    queryFn: apiClient.getCurrentUserProfile
  });

  return (
    <div>
      <SectionHeader
        title="Profile Management"
        description="Keep structured profile data accurate so the matching engine can evaluate eligibility reliably."
      />

      <Card>
        <CardHeader>
          <CardTitle>Eligibility Data Profile</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Full name</Label>
              <Input defaultValue={profile?.fullName} />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input type="email" defaultValue={profile?.email} />
            </div>
            <div className="space-y-2">
              <Label>Country</Label>
              <Input defaultValue={profile?.country} />
            </div>
            <div className="space-y-2">
              <Label>Organization type</Label>
              <Input defaultValue={profile?.organizationType} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>Sectors</Label>
              <Input defaultValue={profile?.sectors.join(", ")} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>Funding needs</Label>
              <Textarea defaultValue={profile?.fundingNeeds.join(", ")} />
            </div>
            <div className="md:col-span-2">
              <Button type="button">Save profile changes</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
