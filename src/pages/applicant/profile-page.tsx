import { SectionHeader } from "@/components/shared/section-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { User, Building2, TrendingUp, DollarSign, Loader2 } from "lucide-react";
import PersonalDetails from "@/components/applicant/profile/personal";
import { useProfile, useUpdateProfile } from "@/hooks/use-profile";
import BusinessDetail from "@/components/applicant/profile/business-details";
import { UserProfileView } from "@/types/api";
import FundingRequirements from "@/components/applicant/profile/funding-requirements";
import BusinessMetrics from "@/components/applicant/profile/business-metrics";
import {
  saveBusinessDetails,
  saveBusinessMetrics,
  // savePersonalDetails,
  saveFundingRequirements,
} from "@/services/api/profile";
import { toast } from "sonner";

export function ApplicantProfilePage() {
  const { data, isLoading } = useProfile();
  const updateProfile = useUpdateProfile();
  console.log(data);

  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState<UserProfileView>(
    data ? data[0] : ({} as UserProfileView),
  );

  useEffect(() => {
    if (data && data.length > 0) {
      setProfile(data[0]);
      console.log("Profile data loaded:", data[0]);
    }
  }, [data]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex bg-background">
        <div className="flex-1 flex flex-col pb-16 md:pb-0">
          <main className="flex-1 py-6 mx-auto w-full">
            <div className="mb-6">
              <Skeleton className="h-9 w-64 mb-2" />
              <Skeleton className="h-5 w-96" />
            </div>

            <Card className="mb-6 pt-4">
              <CardContent className="flex space-x-4 w-full">
                <Skeleton className="flex-1 h-10" />
                <Skeleton className="flex-1 h-10" />
                <Skeleton className="flex-1 h-10" />
                <Skeleton className="flex-1 h-10" />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-48" />
              </CardHeader>
              <CardContent className="space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </CardContent>
            </Card>
          </main>
        </div>
      </div>
    );
  }

  const handleSave = async () => {
    setSaving(true);
    updateProfile.mutate(profile, {
      onSuccess: () => {
        toast.promise(
          Promise.allSettled([
            saveBusinessDetails(profile),
            saveBusinessMetrics(profile),
            saveFundingRequirements(profile),
          ]),
          {
            loading: "Saving Progress...",
            success: () => {
              setSaving(false);
              return "Changes saved successfully!";
            },
            error: (error) => {
              setSaving(false);
              return `Error saving progress: ${error.message || error}`;
            },
          },
        );
      }, 
      onError: () => {
        toast.error("Error updating profile. Please try again.");
        setSaving(false);
      }
    })
  };

  return (
    <div>
      <SectionHeader
        title="Profile Management"
        description="Keep structured profile data accurate so the matching engine can evaluate eligibility reliably."
      />

      <Tabs defaultValue="personal" className="w-full">
        <TabsList className="flex gap-2 flex-wrap h-fit">
          <TabsTrigger
            className="flex-1 flex gap-1 items-center"
            value="personal"
          >
            <User className="h-4 w-4" /> Personal Information
          </TabsTrigger>
          <TabsTrigger
            className="flex-1 flex gap-1 items-center"
            value="business-details"
          >
            <Building2 className="h-4 w-4" /> Business Details
          </TabsTrigger>
          <TabsTrigger
            className="flex-1 flex gap-1 items-center"
            value="business-metrics"
          >
            <TrendingUp className="h-4 w-4" /> Business Metrics
          </TabsTrigger>
          <TabsTrigger
            className="flex-1 flex gap-1 items-center"
            value="funding-requirements"
          >
            <DollarSign className="h-4 w-4" /> Funding Requirements
          </TabsTrigger>
        </TabsList>

        <TabsContent value="personal">
          <PersonalDetails profile={profile} setProfile={setProfile} />
        </TabsContent>

        <TabsContent value="business-details">
          <BusinessDetail profile={profile} setProfile={setProfile} />
        </TabsContent>

        <TabsContent value="business-metrics">
          <BusinessMetrics profile={profile} setProfile={setProfile} />
        </TabsContent>

        <TabsContent value="funding-requirements">
          <FundingRequirements profile={profile} setProfile={setProfile} />
        </TabsContent>
      </Tabs>

      <div className="flex justify-end gap-4">
        <Button variant="outline" onClick={() => navigate("/dashboard")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            "Save Changes"
          )}
        </Button>
      </div>
    </div>
  );
}
